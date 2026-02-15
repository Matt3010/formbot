<?php

namespace App\Http\Controllers;

use App\Http\Resources\AnalysisResource;
use App\Models\Analysis;
use App\Services\ScraperClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;

class AnalysisController extends Controller
{
    /**
     * List analyses for the authenticated user.
     */
    public function index(Request $request): JsonResponse
    {
        $query = Analysis::where('user_id', auth()->id())
            ->orderByDesc('created_at');

        if ($request->has('status')) {
            $query->where('status', $request->input('status'));
        }

        $analyses = $query->paginate(25);

        return AnalysisResource::collection($analyses)->response();
    }

    /**
     * Show a single analysis.
     */
    public function show(Analysis $analysis): JsonResponse
    {
        if ($analysis->user_id !== auth()->id()) {
            abort(403);
        }

        return (new AnalysisResource($analysis))->response();
    }

    /**
     * Cancel a running analysis.
     */
    public function cancel(Analysis $analysis, ScraperClient $scraperClient): JsonResponse
    {
        if ($analysis->user_id !== auth()->id()) {
            abort(403);
        }

        if (!in_array($analysis->status, ['pending', 'analyzing'])) {
            return response()->json([
                'message' => 'Only pending or analyzing analyses can be cancelled.',
            ], 422);
        }

        try {
            $scraperClient->cancelAnalysis($analysis->id);
        } catch (\Exception $e) {
            Log::warning('Failed to cancel analysis on scraper', [
                'analysis_id' => $analysis->id,
                'error' => $e->getMessage(),
            ]);
        }

        $analysis->update([
            'status' => 'failed',
            'error' => 'Cancelled by user',
            'completed_at' => now(),
        ]);

        return response()->json(['message' => 'Analysis cancelled.']);
    }

    /**
     * Link an analysis to a task.
     */
    public function linkTask(Analysis $analysis, Request $request): JsonResponse
    {
        if ($analysis->user_id !== auth()->id()) {
            abort(403);
        }

        $request->validate([
            'task_id' => ['required', 'uuid', 'exists:tasks,id'],
        ]);

        $analysis->update(['task_id' => $request->input('task_id')]);

        return response()->json(['message' => 'Analysis linked to task.']);
    }

    /**
     * Internal callback from scraper to store analysis result.
     */
    public function storeResult(string $id, Request $request): JsonResponse
    {
        $internalKey = config('scraper.internal_key');
        if ($request->header('X-Internal-Key') !== $internalKey) {
            abort(403, 'Invalid internal key.');
        }

        $analysis = Analysis::find($id);
        if (!$analysis) {
            return response()->json(['message' => 'Analysis not found.'], 404);
        }

        // Don't update if already failed/cancelled
        if ($analysis->status === 'failed') {
            return response()->json(['message' => 'Analysis already failed or cancelled.']);
        }

        $error = $request->input('error');
        $analysis->update([
            'status' => $error ? 'failed' : 'completed',
            'result' => $request->input('result'),
            'error' => $error,
            'completed_at' => now(),
        ]);

        return response()->json(['message' => 'Result stored.']);
    }
}
