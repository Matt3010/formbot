<?php

namespace App\Http\Controllers;

use App\Http\Resources\ExecutionLogResource;
use App\Models\ExecutionLog;
use App\Models\Task;
use App\Services\ScraperClient;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\AnonymousResourceCollection;
use Illuminate\Support\Facades\Storage;

class ExecutionController extends Controller
{
    /**
     * Display a listing of execution logs for a task.
     */
    public function index(Task $task): AnonymousResourceCollection
    {
        $this->authorizeTask($task);

        $executions = $task->executionLogs()
            ->orderBy('created_at', 'desc')
            ->paginate(15);

        return ExecutionLogResource::collection($executions);
    }

    /**
     * Display the specified execution log.
     */
    public function show(ExecutionLog $execution): ExecutionLogResource
    {
        $execution->load('task');
        $this->authorizeTask($execution->task);

        return new ExecutionLogResource($execution);
    }

    /**
     * Return the screenshot file for an execution.
     */
    public function screenshot(ExecutionLog $execution): mixed
    {
        $execution->load('task');
        $this->authorizeTask($execution->task);

        if (!$execution->screenshot_path) {
            return response()->json(['message' => 'Screenshot not found.'], 404);
        }

        // Support both legacy plain filenames and explicit relative paths.
        $candidates = [
            $execution->screenshot_path,
            'screenshots/' . ltrim($execution->screenshot_path, '/'),
        ];

        $resolvedPath = null;
        foreach ($candidates as $candidate) {
            if (Storage::disk('local')->exists($candidate)) {
                $resolvedPath = $candidate;
                break;
            }
        }

        if (!$resolvedPath) {
            return response()->json(['message' => 'Screenshot not found.'], 404);
        }

        return response()->file(Storage::disk('local')->path($resolvedPath));
    }

    /**
     * Upload a file for task execution.
     */
    public function uploadFile(Request $request): JsonResponse
    {
        $request->validate([
            'file' => ['required', 'file', 'max:10240'],
        ]);

        $path = $request->file('file')->store('uploads', 'local');

        return response()->json([
            'path' => $path,
            'filename' => basename($path),
        ]);
    }

    /**
     * Delete an uploaded file.
     */
    public function deleteFile(string $filename): JsonResponse
    {
        $path = 'uploads/' . $filename;

        if (!Storage::disk('local')->exists($path)) {
            return response()->json(['message' => 'File not found.'], 404);
        }

        Storage::disk('local')->delete($path);

        return response()->json(['message' => 'File deleted successfully.']);
    }

    /**
     * Get recent execution logs across all tasks for the authenticated user.
     */
    public function logs(Request $request): AnonymousResourceCollection
    {
        $query = ExecutionLog::whereHas('task', function ($query) use ($request) {
            $query->where('user_id', $request->user()->id);
        })
            ->with('task')
            ->orderBy('created_at', 'desc');

        if ($request->filled('status')) {
            $query->where('status', $request->input('status'));
        }

        $executions = $query->paginate($request->input('per_page', 25));

        return ExecutionLogResource::collection($executions);
    }

    /**
     * Resume execution after manual VNC intervention.
     */
    public function resume(ExecutionLog $execution): JsonResponse
    {
        $execution->load('task');
        $this->authorizeTask($execution->task);

        if (!$execution->vnc_session_id) {
            return response()->json(['message' => 'No VNC session for this execution.'], 400);
        }

        $scraperClient = app(ScraperClient::class);
        $result = $scraperClient->resumeVnc($execution->vnc_session_id, (string) $execution->id);

        return response()->json($result);
    }

    /**
     * Abort execution (stop VNC session).
     */
    public function abort(ExecutionLog $execution): JsonResponse
    {
        $execution->load('task');
        $this->authorizeTask($execution->task);

        if ($execution->vnc_session_id) {
            $scraperClient = app(ScraperClient::class);
            $scraperClient->stopVnc($execution->vnc_session_id);
        }

        $execution->update([
            'status' => 'failed',
            'error_message' => 'Aborted by user',
            'completed_at' => now(),
        ]);

        return response()->json(['message' => 'Execution aborted.']);
    }

    /**
     * Authorize that the authenticated user owns the task.
     */
    private function authorizeTask(Task $task): void
    {
        if ($task->user_id !== request()->user()->id) {
            abort(403, 'Unauthorized access to this task.');
        }
    }
}
