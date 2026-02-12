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
    public function analyze(string $url, ?string $model = null, ?string $analysisId = null): array
    {
        $payload = ['url' => $url];

        if ($model) {
            $payload['ollama_model'] = $model;
        }

        if ($analysisId) {
            $payload['analysis_id'] = $analysisId;
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
    public function execute(string $taskId, bool $isDryRun = false, array $options = [], ?string $executionId = null): array
    {
        $payload = [
            'task_id' => $taskId,
            'is_dry_run' => $isDryRun,
            'stealth_enabled' => $options['stealth_enabled'] ?? true,
            'user_agent' => $options['custom_user_agent'] ?? null,
            'action_delay_ms' => $options['action_delay_ms'] ?? 500,
        ];

        if ($executionId) {
            $payload['execution_id'] = $executionId;
        }

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
     * Analyze login and target pages via the Python scraper service.
     */
    public function analyzeLoginAndTarget(
        string $analysisId,
        string $loginUrl,
        string $targetUrl,
        string $loginFormSelector,
        string $loginSubmitSelector,
        array $loginFields,
        bool $needsVnc = false,
        ?string $model = null,
    ): array {
        $payload = [
            'analysis_id' => $analysisId,
            'login_url' => $loginUrl,
            'target_url' => $targetUrl,
            'login_form_selector' => $loginFormSelector,
            'login_submit_selector' => $loginSubmitSelector,
            'login_fields' => $loginFields,
            'needs_vnc' => $needsVnc,
        ];

        if ($model) {
            $payload['ollama_model'] = $model;
        }

        $response = Http::timeout($this->timeout)
            ->post("{$this->baseUrl}/analyze/login-and-target", $payload);

        if (!$response->successful()) {
            Log::error('Scraper analyzeLoginAndTarget failed', [
                'login_url' => $loginUrl,
                'target_url' => $targetUrl,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            throw new \RuntimeException(
                'Failed to analyze login and target: ' . ($response->json('detail') ?? $response->body())
            );
        }

        return $response->json();
    }

    /**
     * Resume VNC session during analysis.
     */
    public function resumeAnalysisVnc(string $sessionId, string $analysisId): array
    {
        $response = Http::timeout($this->timeout)
            ->post("{$this->baseUrl}/vnc/resume-analysis", [
                'session_id' => $sessionId,
                'analysis_id' => $analysisId,
            ]);

        if (!$response->successful()) {
            throw new \RuntimeException(
                'Failed to resume analysis VNC: ' . ($response->json('detail') ?? $response->body())
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
