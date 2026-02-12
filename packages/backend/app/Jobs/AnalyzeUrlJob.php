<?php

namespace App\Jobs;

use App\Events\AnalysisCompleted;
use App\Models\Analysis;
use App\Services\ScraperClient;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Log;

class AnalyzeUrlJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 1;
    public int $timeout = 600;

    public function __construct(
        public string $analysisId,
        public int $userId,
        public string $url,
        public ?string $model = null,
    ) {}

    public function handle(ScraperClient $scraperClient): void
    {
        Log::info('AnalyzeUrlJob started', [
            'analysis_id' => $this->analysisId,
            'url' => $this->url,
        ]);

        $analysis = Analysis::find($this->analysisId);
        if ($analysis && $analysis->status !== 'cancelled') {
            $analysis->update(['status' => 'analyzing', 'started_at' => now()]);
        }

        try {
            $result = $scraperClient->analyze($this->url, $this->model, $this->analysisId);

            // Check if scraper returned an error in the response body
            $scraperError = $result['error'] ?? null;

            // Update Analysis record (skip if cancelled)
            if ($analysis && $analysis->fresh()->status !== 'cancelled') {
                $analysis->update([
                    'status' => $scraperError ? 'failed' : 'completed',
                    'result' => $result,
                    'error' => $scraperError,
                    'completed_at' => now(),
                ]);
            }

            broadcast(new AnalysisCompleted(
                analysisId: $this->analysisId,
                userId: $this->userId,
                result: $result,
                error: $scraperError,
            ));

            Log::info('AnalyzeUrlJob completed', [
                'analysis_id' => $this->analysisId,
                'forms_count' => count($result['forms'] ?? []),
                'scraper_error' => $scraperError,
            ]);
        } catch (\Exception $e) {
            Log::error('AnalyzeUrlJob failed', [
                'analysis_id' => $this->analysisId,
                'error' => $e->getMessage(),
            ]);

            if ($analysis && $analysis->fresh()->status !== 'cancelled') {
                $analysis->update([
                    'status' => 'failed',
                    'error' => $e->getMessage(),
                    'completed_at' => now(),
                ]);
            }

            broadcast(new AnalysisCompleted(
                analysisId: $this->analysisId,
                userId: $this->userId,
                result: [],
                error: $e->getMessage(),
            ));
        }
    }
}
