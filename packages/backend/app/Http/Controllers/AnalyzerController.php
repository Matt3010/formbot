<?php

namespace App\Http\Controllers;

use App\Http\Requests\AnalyzeUrlRequest;
use App\Jobs\AnalyzeUrlJob;
use App\Jobs\AnalyzeLoginAndTargetJob;
use App\Models\Analysis;
use App\Models\AppSetting;
use App\Services\CryptoService;
use App\Services\ScraperClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Str;

class AnalyzerController extends Controller
{
    /**
     * Analyze a URL to detect forms (async via queue + WebSocket).
     */
    public function analyze(AnalyzeUrlRequest $request): JsonResponse
    {
        $model = $request->input('model') ?? AppSetting::get('ollama_model');

        $analysis = Analysis::create([
            'user_id' => auth()->id(),
            'url' => $request->input('url'),
            'type' => 'simple',
            'status' => 'pending',
            'model' => $model,
        ]);

        AnalyzeUrlJob::dispatch(
            analysisId: $analysis->id,
            userId: auth()->id(),
            url: $request->input('url'),
            model: $model,
        );

        return response()->json([
            'analysis_id' => $analysis->id,
            'message' => 'Analysis started. Results will be sent via WebSocket.',
        ]);
    }

    /**
     * Analyze the next page in a multi-page flow (async via queue + WebSocket).
     */
    public function analyzeNextPage(Request $request): JsonResponse
    {
        $request->validate([
            'url' => ['required', 'url'],
            'session_id' => ['sometimes', 'string'],
            'cookies' => ['sometimes', 'array'],
        ]);

        $model = $request->input('model') ?? AppSetting::get('ollama_model');

        $analysis = Analysis::create([
            'user_id' => auth()->id(),
            'url' => $request->input('url'),
            'type' => 'next_page',
            'status' => 'pending',
            'model' => $model,
        ]);

        AnalyzeUrlJob::dispatch(
            analysisId: $analysis->id,
            userId: auth()->id(),
            url: $request->input('url'),
            model: $model,
        );

        return response()->json([
            'analysis_id' => $analysis->id,
            'message' => 'Analysis started. Results will be sent via WebSocket.',
        ]);
    }

    /**
     * Analyze login page and target page in sequence (async via queue + WebSocket).
     */
    public function analyzeLoginAndTarget(Request $request): JsonResponse
    {
        $request->validate([
            'login_url' => ['required', 'url'],
            'target_url' => ['required', 'url'],
            'login_form_selector' => ['required', 'string'],
            'login_submit_selector' => ['required', 'string'],
            'login_fields' => ['required', 'array'],
            'login_fields.*.field_selector' => ['required', 'string'],
            'login_fields.*.value' => ['required', 'string'],
            'login_fields.*.is_sensitive' => ['sometimes', 'boolean'],
            'needs_vnc' => ['sometimes', 'boolean'],
        ]);

        $model = $request->input('model') ?? AppSetting::get('ollama_model');
        $crypto = app(CryptoService::class);

        $analysis = Analysis::create([
            'user_id' => auth()->id(),
            'url' => $request->input('target_url'),
            'target_url' => $request->input('target_url'),
            'login_url' => $request->input('login_url'),
            'type' => 'login_and_target',
            'status' => 'pending',
            'model' => $model,
        ]);

        // Encrypt sensitive field values
        $loginFields = collect($request->input('login_fields'))->map(function ($field) use ($crypto) {
            if (!empty($field['is_sensitive']) && !empty($field['value'])) {
                $field['value'] = $crypto->encrypt($field['value']);
                $field['encrypted'] = true;
            }
            return $field;
        })->toArray();

        AnalyzeLoginAndTargetJob::dispatch(
            analysisId: $analysis->id,
            userId: auth()->id(),
            loginUrl: $request->input('login_url'),
            targetUrl: $request->input('target_url'),
            loginFormSelector: $request->input('login_form_selector'),
            loginSubmitSelector: $request->input('login_submit_selector'),
            loginFields: $loginFields,
            needsVnc: $request->boolean('needs_vnc', false),
            model: $model,
        );

        return response()->json([
            'analysis_id' => $analysis->id,
            'message' => 'Login-aware analysis started. Results will be sent via WebSocket.',
        ]);
    }

    /**
     * Resume VNC session during analysis.
     */
    public function resumeAnalysisVnc(Request $request): JsonResponse
    {
        $request->validate([
            'session_id' => ['required', 'string'],
            'analysis_id' => ['required', 'string'],
        ]);

        $scraperClient = app(ScraperClient::class);

        $result = $scraperClient->resumeAnalysisVnc(
            sessionId: $request->input('session_id'),
            analysisId: $request->input('analysis_id'),
        );

        return response()->json($result);
    }

    /**
     * Validate CSS selectors on a page (remains synchronous - fast operation).
     */
    public function validateSelectors(Request $request): JsonResponse
    {
        $request->validate([
            'url' => ['required', 'url'],
            'selectors' => ['required', 'array'],
            'selectors.*' => ['required', 'string'],
        ]);

        $scraperClient = app(\App\Services\ScraperClient::class);

        $result = $scraperClient->validateSelectors(
            url: $request->input('url'),
            selectors: $request->input('selectors'),
        );

        return response()->json($result);
    }
}
