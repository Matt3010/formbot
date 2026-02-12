<?php

use App\Models\Analysis;
use Illuminate\Support\Facades\Broadcast;

Broadcast::channel('tasks.{userId}', function ($user, $userId) {
    return (int) $user->id === (int) $userId;
});

Broadcast::channel('execution.{executionId}', function ($user, $executionId) {
    return true; // All authenticated users can listen
});

Broadcast::channel('analysis.{analysisId}', function ($user, $analysisId) {
    $analysis = Analysis::find($analysisId);
    return $analysis && $analysis->user_id === $user->id;
});
