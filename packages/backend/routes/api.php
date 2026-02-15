<?php

use Illuminate\Support\Facades\Broadcast;
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\TaskController;
use App\Http\Controllers\AnalyzerController;
use App\Http\Controllers\ExecutionController;
use App\Http\Controllers\SettingsController;

// Broadcast auth route for private WebSocket channels
Broadcast::routes(['middleware' => ['auth:api'], 'prefix' => '']);

// Public routes
Route::post('/register', [AuthController::class, 'register']);
Route::post('/login', [AuthController::class, 'login']);
Route::get('/health', [SettingsController::class, 'health']);

// Protected routes
Route::middleware('auth:api')->group(function () {
    Route::post('/logout', [AuthController::class, 'logout']);
    Route::get('/user', [AuthController::class, 'user']);

    // Tasks CRUD
    Route::apiResource('tasks', TaskController::class);
    Route::post('/tasks/{task}/clone', [TaskController::class, 'clone']);
    Route::post('/tasks/{task}/activate', [TaskController::class, 'activate']);
    Route::post('/tasks/{task}/pause', [TaskController::class, 'pause']);
    Route::post('/tasks/{task}/execute', [TaskController::class, 'execute']);
    Route::post('/tasks/{task}/dry-run', [TaskController::class, 'dryRun']);
    Route::post('/tasks/{task}/export', [TaskController::class, 'export']);
    Route::post('/tasks/import', [TaskController::class, 'import']);

    // Analyzer
    Route::post('/analyze', [AnalyzerController::class, 'analyze']);

    // Executions
    Route::get('/tasks/{task}/executions', [ExecutionController::class, 'index']);
    Route::get('/executions/{execution}', [ExecutionController::class, 'show']);
    Route::get('/executions/{execution}/screenshot', [ExecutionController::class, 'screenshot']);
    Route::delete('/executions/{execution}/screenshot', [ExecutionController::class, 'deleteScreenshot']);
    Route::post('/executions/{execution}/resume', [ExecutionController::class, 'resume']);
    Route::post('/executions/{execution}/abort', [ExecutionController::class, 'abort']);

    // Screenshots
    Route::get('/screenshots', [ExecutionController::class, 'listScreenshots']);
    Route::get('/screenshots/stats', [ExecutionController::class, 'storageStats']);

    // File upload
    Route::post('/files/upload', [ExecutionController::class, 'uploadFile']);
    Route::delete('/files/{filename}', [ExecutionController::class, 'deleteFile']);

    // Settings
    Route::get('/settings', [SettingsController::class, 'index']);
    Route::put('/settings', [SettingsController::class, 'update']);

    // Task Editing (VNC form editor)
    Route::prefix('tasks/{task}/editing')->group(function () {
        Route::post('/start', [TaskController::class, 'startEditing']);
        Route::post('/resume', [TaskController::class, 'resumeEditing']);
        Route::patch('/draft', [TaskController::class, 'saveDraft']);
        Route::post('/command', [TaskController::class, 'sendCommand']);
        Route::post('/confirm', [TaskController::class, 'confirmEditing']);
        Route::post('/cancel', [TaskController::class, 'cancelEditing']);
        Route::post('/step', [TaskController::class, 'navigateStep']);
        Route::post('/execute-login', [TaskController::class, 'executeLogin']);
        Route::post('/resume-login', [TaskController::class, 'resumeLogin']);
    });

    // Logs
    Route::get('/logs', [ExecutionController::class, 'logs']);
});
