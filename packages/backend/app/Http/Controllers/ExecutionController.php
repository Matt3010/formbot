<?php

namespace App\Http\Controllers;

use App\Http\Resources\ExecutionLogResource;
use App\Models\ExecutionLog;
use App\Models\Task;
use App\Services\ScraperClient;
use App\Services\ScreenshotStorage;
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
     * Return the screenshot for an execution.
     * Returns presigned URL for MinIO screenshots, or file for legacy filesystem screenshots.
     */
    public function screenshot(ExecutionLog $execution, ScreenshotStorage $screenshotStorage): mixed
    {
        $execution->load('task');
        $this->authorizeTask($execution->task);

        // Check for MinIO screenshot (new system)
        if ($execution->screenshot_url) {
            if ($screenshotStorage->exists($execution->screenshot_url)) {
                $presignedUrl = $screenshotStorage->getPresignedUrl($execution->screenshot_url);
                if ($presignedUrl) {
                    return response()->json([
                        'url' => $presignedUrl,
                        'expires_in' => $screenshotStorage->getPresignedUrlExpiry() * 60,
                        'storage' => 'minio',
                    ]);
                }
            }
        }

        // Fallback to legacy filesystem screenshot
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
     * Delete a screenshot for an execution.
     */
    public function deleteScreenshot(ExecutionLog $execution, ScreenshotStorage $screenshotStorage): JsonResponse
    {
        $execution->load('task');
        $this->authorizeTask($execution->task);

        $deleted = false;

        // Delete from MinIO if exists
        if ($execution->screenshot_url) {
            if ($screenshotStorage->delete($execution->screenshot_url)) {
                $deleted = true;
            }
        }

        // Delete from filesystem if exists
        if ($execution->screenshot_path) {
            $candidates = [
                $execution->screenshot_path,
                'screenshots/' . ltrim($execution->screenshot_path, '/'),
            ];

            foreach ($candidates as $candidate) {
                if (Storage::disk('local')->exists($candidate)) {
                    Storage::disk('local')->delete($candidate);
                    $deleted = true;
                    break;
                }
            }
        }

        if (!$deleted) {
            return response()->json(['message' => 'Screenshot not found.'], 404);
        }

        // Update execution record
        $execution->update([
            'screenshot_url' => null,
            'screenshot_size' => null,
            'screenshot_path' => null,
        ]);

        return response()->json(['message' => 'Screenshot deleted successfully.']);
    }

    /**
     * List all screenshots with pagination.
     */
    public function listScreenshots(Request $request, ScreenshotStorage $screenshotStorage): JsonResponse
    {
        $user = $request->user();

        $query = ExecutionLog::whereHas('task', function ($query) use ($user) {
            $query->where('user_id', $user->id);
        })
            ->where(function ($query) {
                $query->whereNotNull('screenshot_url')
                    ->orWhereNotNull('screenshot_path');
            })
            ->with('task:id,name')
            ->orderBy('created_at', 'desc');

        $perPage = $request->input('per_page', 25);
        $executions = $query->paginate($perPage);

        $screenshots = $executions->getCollection()->map(function ($execution) use ($screenshotStorage) {
            $hasMinioScreenshot = $execution->screenshot_url && $screenshotStorage->exists($execution->screenshot_url);
            $hasFilesystemScreenshot = false;

            if ($execution->screenshot_path) {
                $candidates = [
                    $execution->screenshot_path,
                    'screenshots/' . ltrim($execution->screenshot_path, '/'),
                ];
                foreach ($candidates as $candidate) {
                    if (Storage::disk('local')->exists($candidate)) {
                        $hasFilesystemScreenshot = true;
                        break;
                    }
                }
            }

            if (!$hasMinioScreenshot && !$hasFilesystemScreenshot) {
                return null;
            }

            return [
                'execution_id' => $execution->id,
                'task_id' => $execution->task_id,
                'task_name' => $execution->task->name ?? 'Unknown',
                'created_at' => $execution->created_at->toIso8601String(),
                'size' => $execution->screenshot_size,
                'storage' => $hasMinioScreenshot ? 'minio' : 'filesystem',
            ];
        })->filter()->values();

        return response()->json([
            'data' => $screenshots,
            'meta' => [
                'current_page' => $executions->currentPage(),
                'last_page' => $executions->lastPage(),
                'per_page' => $executions->perPage(),
                'total' => $executions->total(),
            ],
        ]);
    }

    /**
     * Get storage statistics for screenshots.
     */
    public function storageStats(Request $request, ScreenshotStorage $screenshotStorage): JsonResponse
    {
        $user = $request->user();

        // Get MinIO stats
        $minioStats = $screenshotStorage->getStats();

        // Get filesystem stats for user's screenshots
        $filesystemSize = 0;
        $filesystemCount = 0;

        $executions = ExecutionLog::whereHas('task', function ($query) use ($user) {
            $query->where('user_id', $user->id);
        })
            ->whereNotNull('screenshot_path')
            ->get();

        foreach ($executions as $execution) {
            $candidates = [
                $execution->screenshot_path,
                'screenshots/' . ltrim($execution->screenshot_path, '/'),
            ];
            foreach ($candidates as $candidate) {
                if (Storage::disk('local')->exists($candidate)) {
                    $filesystemSize += Storage::disk('local')->size($candidate);
                    $filesystemCount++;
                    break;
                }
            }
        }

        return response()->json([
            'minio' => [
                'total_size' => $minioStats['total_size'],
                'count' => $minioStats['count'],
            ],
            'filesystem' => [
                'total_size' => $filesystemSize,
                'count' => $filesystemCount,
            ],
            'total' => [
                'total_size' => $minioStats['total_size'] + $filesystemSize,
                'count' => $minioStats['count'] + $filesystemCount,
            ],
        ]);
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
