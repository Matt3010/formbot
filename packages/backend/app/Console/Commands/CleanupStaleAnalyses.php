<?php

namespace App\Console\Commands;

use App\Models\Analysis;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;

class CleanupStaleAnalyses extends Command
{
    protected $signature = 'formbot:cleanup-stale-analyses';

    protected $description = 'Mark stale analyses (pending/analyzing for over 1 hour) as timed_out';

    public function handle(): int
    {
        $cutoff = now()->subHour();

        $count = Analysis::whereIn('status', ['pending', 'analyzing'])
            ->where('created_at', '<', $cutoff)
            ->update([
                'status' => 'timed_out',
                'completed_at' => now(),
            ]);

        if ($count > 0) {
            $this->info("Marked {$count} stale analysis/analyses as timed_out.");
            Log::info('CleanupStaleAnalyses completed', ['count' => $count]);
        } else {
            $this->info('No stale analyses found.');
        }

        // Cleanup expired editing sessions
        $editingCount = Analysis::where('editing_status', 'active')
            ->where('editing_expires_at', '<', now())
            ->update([
                'editing_status' => 'cancelled',
                'status' => 'completed',
            ]);

        if ($editingCount > 0) {
            $this->info("Cancelled {$editingCount} expired editing session(s).");
            Log::info('CleanupStaleAnalyses: expired editing sessions', ['count' => $editingCount]);
        }

        return Command::SUCCESS;
    }
}
