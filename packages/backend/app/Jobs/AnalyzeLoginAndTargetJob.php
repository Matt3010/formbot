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

class AnalyzeLoginAndTargetJob implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 1;
    public int $timeout = 600;

    public function __construct(
        public string $analysisId,
        public int $userId,
        public string $loginUrl,
        public string $targetUrl,
        public string $loginFormSelector,
        public string $loginSubmitSelector,
        public array $loginFields,
        public bool $needsVnc,
        public ?string $model = null,
    ) {}

    public function handle(ScraperClient $scraperClient): void
    {
        Log::info('AnalyzeLoginAndTargetJob started', [
            'analysis_id' => $this->analysisId,
            'login_url' => $this->loginUrl,
            'target_url' => $this->targetUrl,
        ]);

        $analysis = Analysis::find($this->analysisId);
        if ($analysis && $analysis->status !== 'cancelled') {
            $analysis->update(['status' => 'analyzing', 'started_at' => now()]);
        }

        try {
            // The scraper runs this analysis in the background and broadcasts
            // AnalysisCompleted directly via Soketi when done. We only need to
            // start the process; do NOT broadcast here or the frontend will
            // receive a premature {"status":"started"} result.
            // The scraper will call the internal callback to update the Analysis record.
            $scraperClient->analyzeLoginAndTarget(
                analysisId: $this->analysisId,
                loginUrl: $this->loginUrl,
                targetUrl: $this->targetUrl,
                loginFormSelector: $this->loginFormSelector,
                loginSubmitSelector: $this->loginSubmitSelector,
                loginFields: $this->loginFields,
                needsVnc: $this->needsVnc,
                model: $this->model,
            );

            Log::info('AnalyzeLoginAndTargetJob dispatched to scraper', [
                'analysis_id' => $this->analysisId,
            ]);
        } catch (\Exception $e) {
            // Only broadcast on failure to reach the scraper (e.g. scraper is down).
            // If the scraper accepted the request, it handles its own broadcasting.
            Log::error('AnalyzeLoginAndTargetJob failed', [
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
