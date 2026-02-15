<?php

namespace App\Services;

use App\Exceptions\ScraperRequestException;
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
     * Execute a task via the Python scraper service.
     */
    public function execute(string $taskId, bool $isDryRun = false, array $options = [], ?string $executionId = null): array
    {
        $payload = [
            'task_id' => $taskId,
            'is_dry_run' => $isDryRun,
            'stealth_enabled' => true,  // Always enabled
            'user_agent' => $options['custom_user_agent'] ?? null,
            'action_delay_ms' => 0,  // No artificial delay, Playwright handles waits
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
     * Cancel a running analysis on the scraper.
     */
    public function cancelAnalysis(string $analysisId): array
    {
        $response = Http::timeout(30)
            ->post("{$this->baseUrl}/analyze/{$analysisId}/cancel");

        if (!$response->successful()) {
            Log::warning('Scraper cancelAnalysis failed', [
                'analysis_id' => $analysisId,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            throw new \RuntimeException(
                'Failed to cancel analysis: ' . ($response->json('detail') ?? $response->body())
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

    /**
     * Start an interactive analysis session with VNC for field editing.
     */
    public function startInteractiveAnalysis(string $url, string $analysisId, ?array $analysisResult = null): array
    {
        $payload = [
            'url' => $url,
            'analysis_id' => $analysisId,
        ];
        if ($analysisResult) {
            $payload['analysis_result'] = $analysisResult;
        }

        $response = Http::timeout($this->timeout)
            ->post("{$this->baseUrl}/analyze/interactive", $payload);

        if (!$response->successful()) {
            Log::error('Scraper startInteractiveAnalysis failed', [
                'url' => $url,
                'analysis_id' => $analysisId,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            throw new \RuntimeException(
                'Failed to start interactive analysis: ' . ($response->json('detail') ?? $response->body())
            );
        }

        return $response->json();
    }

    /**
     * Send an editing command to the scraper (mode, focus, test-selector, etc.).
     */
    public function sendEditingCommand(string $analysisId, string $command, array $payload = []): array
    {
        $endpointMap = [
            'mode' => '/editing/mode',
            'update-fields' => '/editing/update-fields',
            'focus-field' => '/editing/focus-field',
            'test-selector' => '/editing/test-selector',
            'fill-field' => '/editing/fill-field',
            'read-field-value' => '/editing/read-field-value',
        ];

        $endpoint = $endpointMap[$command] ?? null;
        if (!$endpoint) {
            throw new \RuntimeException("Unknown editing command: {$command}");
        }

        $response = Http::timeout(30)
            ->post("{$this->baseUrl}{$endpoint}", array_merge(
                ['analysis_id' => $analysisId],
                $payload,
            ));

        if (!$response->successful()) {
            $detail = $response->json('detail') ?? $response->body();
            $message = is_array($detail) ? json_encode($detail) : (string) $detail;
            throw new ScraperRequestException(
                "Editing command '{$command}' failed: {$message}",
                $response->status(),
            );
        }

        return $response->json();
    }

    /**
     * Stop an editing session on the scraper (cleanup browser + VNC).
     */
    public function stopEditingSession(string $analysisId): array
    {
        $response = Http::timeout(30)
            ->post("{$this->baseUrl}/editing/cleanup", [
                'analysis_id' => $analysisId,
            ]);

        if (!$response->successful()) {
            Log::warning('Scraper stopEditingSession failed', [
                'analysis_id' => $analysisId,
                'status' => $response->status(),
                'body' => $response->body(),
            ]);

            throw new \RuntimeException(
                'Failed to stop editing session: ' . ($response->json('detail') ?? $response->body())
            );
        }

        return $response->json();
    }

    /**
     * Execute login in an existing editing session (fill + submit + navigate to target).
     */
    public function executeLoginInSession(string $analysisId, array $loginFields, string $targetUrl, string $submitSelector = '', bool $humanBreakpoint = false): array
    {
        $payload = [
            'analysis_id' => $analysisId,
            'login_fields' => $loginFields,
            'target_url' => $targetUrl,
            'submit_selector' => $submitSelector,
            'human_breakpoint' => $humanBreakpoint,
        ];

        $response = Http::timeout($this->timeout)
            ->asJson()
            ->post("{$this->baseUrl}/editing/execute-login", $payload);

        if (!$response->successful()) {
            $detail = $response->json('detail') ?? $response->body();
            $message = is_array($detail) ? json_encode($detail) : (string) $detail;
            throw new ScraperRequestException(
                'Failed to execute login in session: ' . $message,
                $response->status(),
            );
        }

        return $response->json();
    }

    /**
     * Resume login execution after manual intervention in VNC.
     */
    public function resumeLoginInSession(string $analysisId): array
    {
        $response = Http::timeout(30)
            ->post("{$this->baseUrl}/editing/resume-login", [
                'analysis_id' => $analysisId,
            ]);

        if (!$response->successful()) {
            $detail = $response->json('detail') ?? $response->body();
            $message = is_array($detail) ? json_encode($detail) : (string) $detail;
            throw new ScraperRequestException(
                'Failed to resume login: ' . $message,
                $response->status(),
            );
        }

        return $response->json();
    }

    /**
     * Navigate to a different step URL during editing.
     */
    public function navigateEditingStep(string $analysisId, string $url, ?int $step = null, ?string $requestId = null): array
    {
        $payload = [
            'analysis_id' => $analysisId,
            'url' => $url,
        ];

        if ($step !== null) {
            $payload['step'] = $step;
        }
        if ($requestId) {
            $payload['request_id'] = $requestId;
        }

        $response = Http::timeout(30)
            ->post("{$this->baseUrl}/editing/navigate", $payload);

        if (!$response->successful()) {
            $detail = $response->json('detail') ?? $response->body();
            $message = is_array($detail) ? json_encode($detail) : (string) $detail;
            throw new ScraperRequestException(
                'Failed to navigate editing step: ' . $message,
                $response->status(),
            );
        }

        return $response->json();
    }
}
