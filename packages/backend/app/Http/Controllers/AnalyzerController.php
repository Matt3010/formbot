<?php

namespace App\Http\Controllers;

use App\Http\Requests\AnalyzeUrlRequest;
use App\Models\Analysis;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class AnalyzerController extends Controller
{
    /**
     * Analyze a URL — always creates a manual analysis (no AI).
     */
    public function analyze(AnalyzeUrlRequest $request): JsonResponse
    {
        $analysis = Analysis::create([
            'user_id' => auth()->id(),
            'url' => $request->input('url'),
            'type' => 'manual',
            'status' => 'editing',
            'model' => null,
            'result' => [
                'url' => $request->input('url'),
                'page_requires_login' => false,
                'forms' => [[
                    'form_type' => 'target',
                    'form_selector' => '',
                    'submit_selector' => '',
                    'fields' => [],
                    'page_url' => $request->input('url'),
                ]],
            ],
        ]);

        return response()->json([
            'analysis_id' => $analysis->id,
            'message' => 'Manual analysis created. Open the editor to configure fields.',
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
