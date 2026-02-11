<?php

namespace App\Jobs;

use App\Events\CaptchaDetected;
use App\Events\ExecutionCompleted;
use App\Events\ExecutionStarted;
use App\Events\TaskStatusChanged;
use App\Models\ExecutionLog;
use App\Models\Task;
use App\Services\ScraperClient;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;

class ExecuteTaskJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    /**
     * The number of times the job may be attempted.
     */
    public int $tries = 3;

    /**
     * The maximum number of seconds the job can run.
     */
    public int $timeout = 300;

    /**
     * Calculate the number of seconds to wait before retrying the job.
     */
    public function backoff(): array
    {
        return [10, 30, 90];
    }

    /**
     * Create a new job instance.
     */
    public function __construct(
        public Task $task,
        public bool $isDryRun = false,
    ) {}

    /**
     * Execute the job.
     */
    public function handle(ScraperClient $scraperClient): void
    {
        $execution = ExecutionLog::create([
            'task_id' => $this->task->id,
            'started_at' => now(),
            'status' => 'running',
            'is_dry_run' => $this->isDryRun,
        ]);

        event(new ExecutionStarted($execution));

        try {
            $this->task->load('formDefinitions.formFields');

            $result = $scraperClient->execute(
                taskId: $this->task->id,
                isDryRun: $this->isDryRun,
                options: [
                    'stealth_enabled' => $this->task->stealth_enabled,
                    'custom_user_agent' => $this->task->custom_user_agent,
                    'action_delay_ms' => $this->task->action_delay_ms,
                    'max_retries' => $this->task->max_retries,
                ],
            );

            $status = $this->isDryRun ? 'dry_run_ok' : 'success';

            if (isset($result['status'])) {
                $status = match ($result['status']) {
                    'captcha_blocked' => 'captcha_blocked',
                    '2fa_required' => '2fa_required',
                    'waiting_manual' => 'waiting_manual',
                    'failed' => 'failed',
                    default => $status,
                };
            }

            $execution->update([
                'completed_at' => now(),
                'status' => $status,
                'steps_log' => $result['steps'] ?? null,
                'screenshot_path' => $result['screenshot_path'] ?? null,
                'vnc_session_id' => $result['vnc_session_id'] ?? null,
            ]);

            if ($status === 'captcha_blocked') {
                event(new CaptchaDetected($execution));
            }

            // Update task status
            if (!$this->isDryRun && in_array($status, ['success', 'failed'])) {
                $this->task->update(['status' => $status === 'success' ? 'completed' : 'failed']);
                event(new TaskStatusChanged($this->task));
            }

        } catch (\Exception $e) {
            Log::error('Task execution failed', [
                'task_id' => $this->task->id,
                'execution_id' => $execution->id,
                'error' => $e->getMessage(),
            ]);

            $execution->update([
                'completed_at' => now(),
                'status' => 'failed',
                'error_message' => $e->getMessage(),
                'retry_count' => $this->attempts(),
            ]);

            if (!$this->isDryRun) {
                $this->task->update(['status' => 'failed']);
                event(new TaskStatusChanged($this->task));
            }
        }

        event(new ExecutionCompleted($execution->fresh()));
    }

    /**
     * Handle a job failure.
     */
    public function failed(?\Throwable $exception): void
    {
        Log::error('ExecuteTaskJob permanently failed', [
            'task_id' => $this->task->id,
            'error' => $exception?->getMessage(),
        ]);

        $this->task->update(['status' => 'failed']);
        event(new TaskStatusChanged($this->task));
    }
}
