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
        // Create execution record - Python will manage its status from here
        $execution = ExecutionLog::create([
            'task_id' => $this->task->id,
            'started_at' => now(),
            'status' => 'queued',
            'is_dry_run' => $this->isDryRun,
        ]);

        event(new ExecutionStarted($execution));

        try {
            $this->task->load('formDefinitions.formFields');

            // Pass execution_id so Python uses this record instead of creating a new one
            $result = $scraperClient->execute(
                taskId: $this->task->id,
                isDryRun: $this->isDryRun,
                options: [
                    'stealth_enabled' => $this->task->stealth_enabled,
                    'custom_user_agent' => $this->task->custom_user_agent,
                    'action_delay_ms' => $this->task->action_delay_ms,
                    'max_retries' => $this->task->max_retries,
                ],
                executionId: (string) $execution->id,
            );

            // Python runs in background and manages the execution record directly in DB.
            // We don't update the execution here - Python handles status transitions
            // (running -> waiting_manual -> success/failed).

        } catch (\Exception $e) {
            Log::error('Task execution failed', [
                'task_id' => $this->task->id,
                'execution_id' => $execution->id,
                'error' => $e->getMessage(),
            ]);

            // Only update on HTTP-level failure (scraper unreachable, etc.)
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
