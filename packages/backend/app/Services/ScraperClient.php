<?php

namespace App\Services;

use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class ScraperClient
{
    private string $baseUrl;
    private int $timeout;

    public function __construct()
    {
        $this->baseUrl = rtrim(config('scraper.service_url'), '/');
        $this->timeout = (int) config('scraper.timeout', 600);
    }

    /**
     * Analyze a URL to detect forms using the Python scraper service.
     */
    public function analyze(string $url, ?string $model = null): array
    {
        $payload = ['url' => $url];

        if ($model) {
            $payload['ollama_model'] = $model;
        }

        $response = Http::timeout($this->timeout)
            ->post("{$this->baseUrl}/analyze", $payload);

        if (!$response->successful()) {
            Log::error('Scraper analyze failed', [
                'url' => $url,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            throw new \RuntimeException(
                'Failed to analyze URL: ' . ($response->json('detail') ?? $response->body())
            );
        }

        return $response->json();
    }

    /**
     * Execute a task via the Python scraper service.
     */
    public function execute(string $taskId, bool $isDryRun = false, array $options = []): array
    {
        $payload = [
            'task_id' => $taskId,
            'is_dry_run' => $isDryRun,
            'options' => $options,
        ];

        $response = Http::timeout($this->timeout)
            ->post("{$this->baseUrl}/execute", $payload);

        if (!$response->successful()) {
            Log::error('Scraper execute failed', [
                'task_id' => $taskId,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            throw new \RuntimeException(
                'Failed to execute task: ' . ($response->json('detail') ?? $response->body())
            );
        }

        return $response->json();
    }

    /**
     * Validate CSS selectors on a page.
     */
    public function validateSelectors(string $url = '', array $selectors = [], ?string $taskId = null): array
    {
        $payload = [
            'url' => $url,
            'selectors' => $selectors,
        ];

        if ($taskId) {
            $payload['task_id'] = $taskId;
        }

        $response = Http::timeout($this->timeout)
            ->post("{$this->baseUrl}/validate-selectors", $payload);

        if (!$response->successful()) {
            Log::error('Scraper validate selectors failed', [
                'url' => $url,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            throw new \RuntimeException(
                'Failed to validate selectors: ' . ($response->json('detail') ?? $response->body())
            );
        }

        return $response->json();
    }

    /**
     * Start a VNC session for manual intervention.
     */
    public function startVnc(string $executionId): array
    {
        $response = Http::timeout(30)
            ->post("{$this->baseUrl}/vnc/start", [
                'execution_id' => $executionId,
            ]);

        if (!$response->successful()) {
            throw new \RuntimeException(
                'Failed to start VNC session: ' . ($response->json('detail') ?? $response->body())
            );
        }

        return $response->json();
    }

    /**
     * Stop a VNC session.
     */
    public function stopVnc(string $sessionId): array
    {
        $response = Http::timeout(30)
            ->post("{$this->baseUrl}/vnc/stop", [
                'session_id' => $sessionId,
            ]);

        if (!$response->successful()) {
            throw new \RuntimeException(
                'Failed to stop VNC session: ' . ($response->json('detail') ?? $response->body())
            );
        }

        return $response->json();
    }

    /**
     * Resume execution after manual VNC intervention.
     */
    public function resumeVnc(string $sessionId, string $executionId): array
    {
        $response = Http::timeout($this->timeout)
            ->post("{$this->baseUrl}/vnc/resume", [
                'session_id' => $sessionId,
                'execution_id' => $executionId,
            ]);

        if (!$response->successful()) {
            throw new \RuntimeException(
                'Failed to resume VNC session: ' . ($response->json('detail') ?? $response->body())
            );
        }

        return $response->json();
    }
}
