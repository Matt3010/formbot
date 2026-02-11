<?php

use Illuminate\Support\Facades\Broadcast;

Broadcast::channel('tasks.{userId}', function ($user, $userId) {
    return (int) $user->id === (int) $userId;
});

Broadcast::channel('execution.{executionId}', function ($user, $executionId) {
    return true; // All authenticated users can listen
});

// Analysis channels are public (no auth needed) - they use Channel, not PrivateChannel
// in the AnalysisCompleted event, so no authorization callback is needed here.
