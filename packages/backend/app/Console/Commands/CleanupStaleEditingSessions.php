<?php

namespace App\Console\Commands;

use App\Models\Task;
use App\Services\ScraperClient;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;

class CleanupStaleEditingSessions extends Command
{
    protected $signature = 'formbot:cleanup-stale-editing-sessions';

    protected $description = 'Cancel expired task editing sessions (VNC sessions that have expired)';

    public function handle(): int
    {
        // Cleanup expired editing sessions
        $expiredTasks = Task::where('editing_status', 'active')
            ->where('editing_expires_at', '<', now())
            ->get();

        if ($expiredTasks->isEmpty()) {
            $this->info('No expired editing sessions found.');
            return Command::SUCCESS;
        }

        $scraperClient = app(ScraperClient::class);

        // Stop VNC sessions on scraper first
        foreach ($expiredTasks as $task) {
            try {
                $scraperClient->stopEditingSession($task->id);
            } catch (\Exception $e) {
                Log::warning('Failed to stop expired editing session on scraper', [
                    'task_id' => $task->id,
                    'error' => $e->getMessage(),
                ]);
            }
        }

        // Update database
        $count = Task::whereIn('id', $expiredTasks->pluck('id'))
            ->update([
                'editing_status' => 'cancelled',
                'status' => 'draft', // revert to draft
            ]);

        $this->info("Cancelled {$count} expired editing session(s).");
        Log::info('CleanupStaleEditingSessions completed', ['count' => $count]);

        return Command::SUCCESS;
    }
}
