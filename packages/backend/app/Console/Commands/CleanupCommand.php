<?php

namespace App\Console\Commands;

use App\Models\AppSetting;
use App\Models\ExecutionLog;
use App\Services\ScreenshotStorage;
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
    public function handle(ScreenshotStorage $screenshotStorage): int
    {
        $retentionDays = (int) AppSetting::get('retention_days', 30);
        $cutoffDate = now()->subDays($retentionDays);

        $this->info("Cleaning up data older than {$retentionDays} days (before {$cutoffDate->toDateTimeString()})...");

        // Find and delete old execution logs
        $oldExecutions = ExecutionLog::where('created_at', '<', $cutoffDate)->get();

        $deletedLogs = 0;
        $deletedFilesystemScreenshots = 0;
        $deletedMinioScreenshots = 0;

        foreach ($oldExecutions as $execution) {
            // Delete associated MinIO screenshot
            if ($execution->screenshot_url) {
                if ($screenshotStorage->delete($execution->screenshot_url)) {
                    $deletedMinioScreenshots++;
                }
            }

            // Delete associated filesystem screenshot
            if ($execution->screenshot_path && Storage::disk('local')->exists($execution->screenshot_path)) {
                Storage::disk('local')->delete($execution->screenshot_path);
                $deletedFilesystemScreenshots++;
            }

            $execution->delete();
            $deletedLogs++;
        }

        // Clean up orphaned filesystem screenshot files
        if (Storage::disk('local')->exists('screenshots')) {
            $screenshotFiles = Storage::disk('local')->files('screenshots');
            foreach ($screenshotFiles as $file) {
                $lastModified = Storage::disk('local')->lastModified($file);
                if ($lastModified < $cutoffDate->timestamp) {
                    Storage::disk('local')->delete($file);
                    $deletedFilesystemScreenshots++;
                }
            }
        }

        // Clean up orphaned MinIO screenshots
        $deletedMinioScreenshots += $screenshotStorage->deleteOlderThan($cutoffDate);

        $totalDeletedScreenshots = $deletedFilesystemScreenshots + $deletedMinioScreenshots;
        $this->info("Deleted {$deletedLogs} execution log(s) and {$totalDeletedScreenshots} screenshot(s).");
        $this->info("  - Filesystem: {$deletedFilesystemScreenshots}");
        $this->info("  - MinIO: {$deletedMinioScreenshots}");

        Log::info('Cleanup command completed', [
            'execution_logs_deleted' => $deletedLogs,
            'filesystem_screenshots_deleted' => $deletedFilesystemScreenshots,
            'minio_screenshots_deleted' => $deletedMinioScreenshots,
            'retention_days' => $retentionDays,
        ]);

        return Command::SUCCESS;
    }
}
