<?php

namespace App\Http\Controllers;

use App\Http\Requests\AnalyzeUrlRequest;
use App\Jobs\AnalyzeUrlJob;
use App\Models\AppSetting;
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
        $analysisId = (string) Str::uuid();
        $model = $request->input('model') ?? AppSetting::get('ollama_model');

        AnalyzeUrlJob::dispatch(
            analysisId: $analysisId,
            userId: auth()->id(),
            url: $request->input('url'),
            model: $model,
        );

        return response()->json([
            'analysis_id' => $analysisId,
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

        $analysisId = (string) Str::uuid();
        $model = $request->input('model') ?? AppSetting::get('ollama_model');

        AnalyzeUrlJob::dispatch(
            analysisId: $analysisId,
            userId: auth()->id(),
            url: $request->input('url'),
            model: $model,
        );

        return response()->json([
            'analysis_id' => $analysisId,
            'message' => 'Analysis started. Results will be sent via WebSocket.',
        ]);
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
