<?php

namespace App\Http\Controllers;

use App\Events\TaskStatusChanged;
use App\Models\Analysis;
use App\Models\FormDefinition;
use App\Models\FormField;
use App\Models\Task;
use App\Services\CryptoService;
use App\Services\ScraperClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;

class EditingController extends Controller
{
    /**
     * Start a VNC editing session for an analysis.
     */
    public function start(Analysis $analysis, Request $request, ScraperClient $scraperClient): JsonResponse
    {
        $this->authorizeAnalysis($analysis);

        if ($analysis->status !== 'completed' && $analysis->status !== 'editing') {
            return response()->json(['message' => 'Analysis must be completed before editing.'], 422);
        }

        // If a previous session exists, clean it up before starting a new one
        if ($analysis->editing_status === 'active') {
            try {
                $scraperClient->stopEditingSession($analysis->id);
            } catch (\Exception $e) {
                Log::warning('Failed to stop previous editing session', [
                    'analysis_id' => $analysis->id,
                    'error' => $e->getMessage(),
                ]);
            }
        }

        // Allow URL override (e.g., login URL instead of target URL)
        $url = $request->input('url', $analysis->url);

        try {
            $result = $scraperClient->startInteractiveAnalysis(
                url: $url,
                analysisId: $analysis->id,
                analysisResult: $analysis->result,
            );

            $analysis->update([
                'status' => 'editing',
                'editing_status' => 'active',
                'editing_started_at' => now(),
                'editing_expires_at' => now()->addMinutes(30),
            ]);

            return response()->json([
                'status' => 'started',
                'analysis_id' => $analysis->id,
            ]);
        } catch (\Exception $e) {
            Log::error('Failed to start editing session', [
                'analysis_id' => $analysis->id,
                'error' => $e->getMessage(),
            ]);
            return response()->json(['message' => 'Failed to start editing session: ' . $e->getMessage()], 500);
        }
    }

    /**
     * Resume an editing session from a saved draft.
     */
    public function resume(Analysis $analysis, ScraperClient $scraperClient): JsonResponse
    {
        $this->authorizeAnalysis($analysis);

        if (!$analysis->user_corrections) {
            return response()->json(['message' => 'No draft to resume.'], 422);
        }

        try {
            $result = $scraperClient->startInteractiveAnalysis(
                url: $analysis->url,
                analysisId: $analysis->id,
                analysisResult: $analysis->result,
            );

            $analysis->update([
                'status' => 'editing',
                'editing_status' => 'active',
                'editing_started_at' => now(),
                'editing_expires_at' => now()->addMinutes(30),
            ]);

            return response()->json([
                'status' => 'resumed',
                'analysis_id' => $analysis->id,
                'user_corrections' => $analysis->user_corrections,
            ]);
        } catch (\Exception $e) {
            Log::error('Failed to resume editing session', [
                'analysis_id' => $analysis->id,
                'error' => $e->getMessage(),
            ]);
            return response()->json(['message' => 'Failed to resume editing session.'], 500);
        }
    }

    /**
     * Save user corrections as a draft (debounced from frontend).
     */
    public function draft(Analysis $analysis, Request $request): JsonResponse
    {
        $this->authorizeAnalysis($analysis);

        $request->validate([
            'user_corrections' => ['required', 'array'],
        ]);

        $analysis->update([
            'user_corrections' => $request->input('user_corrections'),
        ]);

        return response()->json(['status' => 'draft_saved']);
    }

    /**
     * Proxy a command to the scraper (highlight.update, field.focus, selector.test, etc.).
     */
    public function command(Analysis $analysis, Request $request, ScraperClient $scraperClient): JsonResponse
    {
        $this->authorizeAnalysis($analysis);

        $request->validate([
            'command' => ['required', 'string'],
            'payload' => ['sometimes', 'array'],
        ]);

        try {
            $result = $scraperClient->sendEditingCommand(
                analysisId: $analysis->id,
                command: $request->input('command'),
                payload: $request->input('payload', []),
            );

            return response()->json($result);
        } catch (\Exception $e) {
            return response()->json(['message' => 'Command failed: ' . $e->getMessage()], 500);
        }
    }

    /**
     * Confirm all fields — create/update Task + FormDefinition + FormField.
     */
    public function confirm(Analysis $analysis, Request $request, ScraperClient $scraperClient): JsonResponse
    {
        $this->authorizeAnalysis($analysis);

        $corrections = $request->input('user_corrections') ?: $analysis->user_corrections;
        if (!$corrections || empty($corrections['steps'])) {
            return response()->json(['message' => 'No form data to confirm.'], 422);
        }

        $crypto = app(CryptoService::class);

        // Resolve or create Task
        $task = $analysis->task_id ? Task::find($analysis->task_id) : null;
        if (!$task) {
            $task = Task::create([
                'user_id' => auth()->id(),
                'name' => $request->input('name', 'Task from analysis'),
                'target_url' => $analysis->url,
                'status' => 'draft',
                'requires_login' => collect($corrections['steps'])->contains('form_type', 'login'),
                'login_url' => collect($corrections['steps'])
                    ->firstWhere('form_type', 'login')['page_url'] ?? null,
            ]);
        }

        // Delete existing form definitions (cascade deletes fields)
        $task->formDefinitions()->delete();

        // Recreate from user_corrections
        foreach ($corrections['steps'] as $step) {
            $fd = FormDefinition::create([
                'task_id' => $task->id,
                'step_order' => $step['step_order'] ?? 0,
                'page_url' => $step['page_url'] ?? $analysis->url,
                'form_type' => $step['form_type'] ?? 'target',
                'form_selector' => $step['form_selector'] ?? '',
                'submit_selector' => $step['submit_selector'] ?? '',
                'human_breakpoint' => $step['human_breakpoint'] ?? false,
            ]);

            foreach ($step['fields'] ?? [] as $field) {
                $presetValue = $field['preset_value'] ?? null;
                if (!empty($field['is_sensitive']) && !empty($presetValue)) {
                    $presetValue = $crypto->encrypt($presetValue);
                }

                FormField::create([
                    'form_definition_id' => $fd->id,
                    'field_name' => $field['field_name'] ?? '',
                    'field_type' => $field['field_type'] ?? 'text',
                    'field_selector' => $field['field_selector'] ?? '',
                    'field_purpose' => $field['field_purpose'] ?? null,
                    'preset_value' => $presetValue,
                    'is_sensitive' => $field['is_sensitive'] ?? false,
                    'is_file_upload' => $field['is_file_upload'] ?? false,
                    'is_required' => $field['is_required'] ?? false,
                    'options' => $field['options'] ?? null,
                    'sort_order' => $field['sort_order'] ?? 0,
                ]);
            }
        }

        // Update analysis
        $analysis->update([
            'editing_status' => 'confirmed',
            'task_id' => $task->id,
            'user_corrections' => $corrections,
        ]);

        // Cleanup VNC session
        try {
            $scraperClient->stopEditingSession($analysis->id);
        } catch (\Exception $e) {
            Log::warning('Failed to stop editing session on scraper', [
                'analysis_id' => $analysis->id,
                'error' => $e->getMessage(),
            ]);
        }

        $task->load('formDefinitions.formFields');
        event(new TaskStatusChanged($task));

        return response()->json([
            'status' => 'confirmed',
            'task_id' => $task->id,
            'task' => $task,
        ]);
    }

    /**
     * Execute login in the existing VNC session, then navigate to target and analyze.
     */
    public function executeLogin(Analysis $analysis, Request $request, ScraperClient $scraperClient): JsonResponse
    {
        $this->authorizeAnalysis($analysis);

        $request->validate([
            'login_fields' => ['required', 'array'],
            'target_url' => ['required', 'string'],
            'submit_selector' => ['sometimes', 'string'],
            'human_breakpoint' => ['sometimes', 'boolean'],
        ]);

        try {
            $result = $scraperClient->executeLoginInSession(
                analysisId: $analysis->id,
                loginFields: $request->input('login_fields'),
                targetUrl: $request->input('target_url'),
                submitSelector: $request->input('submit_selector', ''),
                humanBreakpoint: $request->boolean('human_breakpoint', false),
            );

            return response()->json($result);
        } catch (\Exception $e) {
            Log::error('Failed to execute login in session', [
                'analysis_id' => $analysis->id,
                'error' => $e->getMessage(),
            ]);
            return response()->json(['message' => 'Login execution failed: ' . $e->getMessage()], 500);
        }
    }

    /**
     * Resume login execution after manual CAPTCHA/2FA intervention.
     */
    public function resumeLogin(Analysis $analysis, ScraperClient $scraperClient): JsonResponse
    {
        $this->authorizeAnalysis($analysis);

        try {
            $result = $scraperClient->resumeLoginInSession($analysis->id);
            return response()->json($result);
        } catch (\Exception $e) {
            return response()->json(['message' => 'Resume failed: ' . $e->getMessage()], 500);
        }
    }

    /**
     * Cancel editing — close VNC, keep draft.
     */
    public function cancel(Analysis $analysis, ScraperClient $scraperClient): JsonResponse
    {
        $this->authorizeAnalysis($analysis);

        $analysis->update([
            'editing_status' => 'cancelled',
            'status' => 'completed', // revert back to completed
        ]);

        try {
            $scraperClient->stopEditingSession($analysis->id);
        } catch (\Exception $e) {
            Log::warning('Failed to stop editing session on cancel', [
                'analysis_id' => $analysis->id,
                'error' => $e->getMessage(),
            ]);
        }

        return response()->json(['status' => 'cancelled']);
    }

    /**
     * Navigate to a different step in multi-step editing.
     */
    public function step(Analysis $analysis, Request $request, ScraperClient $scraperClient): JsonResponse
    {
        $this->authorizeAnalysis($analysis);

        $request->validate([
            'step' => ['required', 'integer', 'min:0'],
            'url' => ['required', 'url'],
        ]);

        try {
            $result = $scraperClient->navigateEditingStep(
                analysisId: $analysis->id,
                url: $request->input('url'),
            );

            $analysis->update([
                'editing_step' => $request->input('step'),
            ]);

            return response()->json($result);
        } catch (\Exception $e) {
            return response()->json(['message' => 'Navigation failed: ' . $e->getMessage()], 500);
        }
    }

    private function authorizeAnalysis(Analysis $analysis): void
    {
        if ($analysis->user_id !== request()->user()->id) {
            abort(403, 'Unauthorized access to this analysis.');
        }
    }
}
