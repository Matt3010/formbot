<?php

namespace App\Console\Commands;

use App\Jobs\ExecuteTaskJob;
use App\Models\Task;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;
use Cron\CronExpression;

class ScheduleTasksCommand extends Command
{
    /**
     * The name and signature of the console command.
     */
    protected $signature = 'formbot:schedule-tasks';

    /**
     * The console command description.
     */
    protected $description = 'Check and dispatch active tasks with cron schedules that are due to run';

    /**
     * Execute the console command.
     */
    public function handle(): int
    {
        $tasks = Task::where('status', 'active')
            ->where('schedule_type', 'cron')
            ->whereNotNull('schedule_cron')
            ->get();

        $dispatched = 0;

        foreach ($tasks as $task) {
            try {
                $cron = new CronExpression($task->schedule_cron);

                if ($cron->isDue()) {
                    ExecuteTaskJob::dispatch($task, false);
                    $dispatched++;

                    Log::info('Scheduled task dispatched', [
                        'task_id' => $task->id,
                        'name' => $task->name,
                        'cron' => $task->schedule_cron,
                    ]);
                }
            } catch (\Exception $e) {
                Log::error('Failed to evaluate cron schedule', [
                    'task_id' => $task->id,
                    'cron' => $task->schedule_cron,
                    'error' => $e->getMessage(),
                ]);
            }
        }

        // Handle one-time scheduled tasks
        $onceTasks = Task::where('status', 'active')
            ->where('schedule_type', 'once')
            ->whereNotNull('schedule_at')
            ->where('schedule_at', '<=', now())
            ->get();

        foreach ($onceTasks as $task) {
            ExecuteTaskJob::dispatch($task, false);
            $task->update(['status' => 'completed']);
            $dispatched++;

            Log::info('One-time scheduled task dispatched', [
                'task_id' => $task->id,
                'name' => $task->name,
                'schedule_at' => $task->schedule_at,
            ]);
        }

        $this->info("Dispatched {$dispatched} task(s).");

        return Command::SUCCESS;
    }
}
