<?php

namespace App\Console\Commands;

use App\Models\Analysis;
use App\Services\ScraperClient;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Log;

class CleanupStaleAnalyses extends Command
{
    protected $signature = 'formbot:cleanup-stale-analyses';

    protected $description = 'Mark stale analyses (pending/analyzing for over 1 hour) as failed';

    public function handle(): int
    {
        $cutoff = now()->subHour();

        $count = Analysis::whereIn('status', ['pending', 'analyzing'])
            ->where('created_at', '<', $cutoff)
            ->update([
                'status' => 'failed',
                'error' => 'Analysis timed out after 1 hour',
                'completed_at' => now(),
            ]);

        if ($count > 0) {
            $this->info("Marked {$count} stale analysis/analyses as failed (timed out).");
            Log::info('CleanupStaleAnalyses completed', ['count' => $count]);
        } else {
            $this->info('No stale analyses found.');
        }

        // Cleanup expired editing sessions
        $expiredAnalyses = Analysis::where('editing_status', 'active')
            ->where('editing_expires_at', '<', now())
            ->get();

        if ($expiredAnalyses->isNotEmpty()) {
            $scraperClient = app(ScraperClient::class);

            // Stop VNC sessions on scraper first
            foreach ($expiredAnalyses as $analysis) {
                try {
                    $scraperClient->stopEditingSession($analysis->id);
                } catch (\Exception $e) {
                    Log::warning('Failed to stop expired editing session on scraper', [
                        'analysis_id' => $analysis->id,
                        'error' => $e->getMessage(),
                    ]);
                }
            }

            // Update database
            $editingCount = Analysis::whereIn('id', $expiredAnalyses->pluck('id'))
                ->update([
                    'editing_status' => 'cancelled',
                    'status' => 'completed',
                ]);

            $this->info("Cancelled {$editingCount} expired editing session(s).");
            Log::info('CleanupStaleAnalyses: expired editing sessions', ['count' => $editingCount]);
        }

        return Command::SUCCESS;
    }
}
