<?php

namespace App\Console\Commands;

use App\Models\AppSetting;
use App\Models\ExecutionLog;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;

class CleanupCommand extends Command
{
    /**
     * The name and signature of the console command.
     */
    protected $signature = 'formbot:cleanup';

    /**
     * The console command description.
     */
    protected $description = 'Delete old execution logs and orphaned screenshots based on retention settings';

    /**
     * Execute the console command.
     */
    public function handle(): int
    {
        $retentionDays = (int) AppSetting::get('retention_days', 30);
        $cutoffDate = now()->subDays($retentionDays);

        $this->info("Cleaning up data older than {$retentionDays} days (before {$cutoffDate->toDateTimeString()})...");

        // Find and delete old execution logs
        $oldExecutions = ExecutionLog::where('created_at', '<', $cutoffDate)->get();

        $deletedLogs = 0;
        $deletedScreenshots = 0;

        foreach ($oldExecutions as $execution) {
            // Delete associated screenshot file
            if ($execution->screenshot_path && Storage::disk('local')->exists($execution->screenshot_path)) {
                Storage::disk('local')->delete($execution->screenshot_path);
                $deletedScreenshots++;
            }

            $execution->delete();
            $deletedLogs++;
        }

        // Clean up orphaned screenshot files
        if (Storage::disk('local')->exists('screenshots')) {
            $screenshotFiles = Storage::disk('local')->files('screenshots');
            foreach ($screenshotFiles as $file) {
                $lastModified = Storage::disk('local')->lastModified($file);
                if ($lastModified < $cutoffDate->timestamp) {
                    Storage::disk('local')->delete($file);
                    $deletedScreenshots++;
                }
            }
        }

        $this->info("Deleted {$deletedLogs} execution log(s) and {$deletedScreenshots} screenshot(s).");

        Log::info('Cleanup command completed', [
            'execution_logs_deleted' => $deletedLogs,
            'screenshots_deleted' => $deletedScreenshots,
            'retention_days' => $retentionDays,
        ]);

        return Command::SUCCESS;
    }
}
