<?php

namespace App\Jobs;

use App\Models\AppSetting;
use App\Models\ExecutionLog;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;

class CleanupOldDataJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    /**
     * Execute the job.
     */
    public function handle(): void
    {
        $retentionDays = (int) AppSetting::get('retention_days', 30);
        $cutoffDate = now()->subDays($retentionDays);

        // Find old execution logs with screenshots
        $oldExecutions = ExecutionLog::where('created_at', '<', $cutoffDate)->get();

        $deletedCount = 0;
        $screenshotsDeleted = 0;

        foreach ($oldExecutions as $execution) {
            // Delete screenshot file if exists
            if ($execution->screenshot_path && Storage::disk('local')->exists($execution->screenshot_path)) {
                Storage::disk('local')->delete($execution->screenshot_path);
                $screenshotsDeleted++;
            }

            $execution->delete();
            $deletedCount++;
        }

        // Clean up orphaned screenshot files
        $screenshotFiles = Storage::disk('local')->files('screenshots');
        foreach ($screenshotFiles as $file) {
            $lastModified = Storage::disk('local')->lastModified($file);
            if ($lastModified < $cutoffDate->timestamp) {
                Storage::disk('local')->delete($file);
                $screenshotsDeleted++;
            }
        }

        Log::info('Cleanup completed', [
            'execution_logs_deleted' => $deletedCount,
            'screenshots_deleted' => $screenshotsDeleted,
            'retention_days' => $retentionDays,
        ]);
    }
}
