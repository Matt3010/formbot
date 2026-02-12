<?php

use Illuminate\Support\Facades\Broadcast;
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\AuthController;
use App\Http\Controllers\TaskController;
use App\Http\Controllers\AnalyzerController;
use App\Http\Controllers\AnalysisController;
use App\Http\Controllers\EditingController;
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
    Route::post('/analyze/next-page', [AnalyzerController::class, 'analyzeNextPage']);
    Route::post('/analyze/login-and-target', [AnalyzerController::class, 'analyzeLoginAndTarget']);
    Route::post('/analyze/resume-vnc', [AnalyzerController::class, 'resumeAnalysisVnc']);
    Route::post('/validate-selectors', [AnalyzerController::class, 'validateSelectors']);

    // Executions
    Route::get('/tasks/{task}/executions', [ExecutionController::class, 'index']);
    Route::get('/executions/{execution}', [ExecutionController::class, 'show']);
    Route::get('/executions/{execution}/screenshot', [ExecutionController::class, 'screenshot']);
    Route::post('/executions/{execution}/resume', [ExecutionController::class, 'resume']);
    Route::post('/executions/{execution}/abort', [ExecutionController::class, 'abort']);

    // File upload
    Route::post('/files/upload', [ExecutionController::class, 'uploadFile']);
    Route::delete('/files/{filename}', [ExecutionController::class, 'deleteFile']);

    // Settings
    Route::get('/settings', [SettingsController::class, 'index']);
    Route::put('/settings', [SettingsController::class, 'update']);

    // Analyses
    Route::get('/analyses', [AnalysisController::class, 'index']);
    Route::get('/analyses/{analysis}', [AnalysisController::class, 'show']);
    Route::post('/analyses/{analysis}/cancel', [AnalysisController::class, 'cancel']);
    Route::post('/analyses/{analysis}/link-task', [AnalysisController::class, 'linkTask']);

    // Editing (VNC form editor)
    Route::prefix('analyses/{analysis}/editing')->group(function () {
        Route::post('/start', [EditingController::class, 'start']);
        Route::post('/resume', [EditingController::class, 'resume']);
        Route::patch('/draft', [EditingController::class, 'draft']);
        Route::post('/command', [EditingController::class, 'command']);
        Route::post('/confirm', [EditingController::class, 'confirm']);
        Route::post('/cancel', [EditingController::class, 'cancel']);
        Route::post('/step', [EditingController::class, 'step']);
    });

    // Logs
    Route::get('/logs', [ExecutionController::class, 'logs']);
});

// Internal routes (scraper callback, protected by X-Internal-Key header)
Route::post('/internal/analyses/{id}/result', [AnalysisController::class, 'storeResult']);
