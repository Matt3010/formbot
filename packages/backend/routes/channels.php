<?php

use App\Models\Task;
use Illuminate\Support\Facades\Broadcast;

Broadcast::channel('tasks.{userId}', function ($user, $userId) {
    return (int) $user->id === (int) $userId;
});

Broadcast::channel('execution.{executionId}', function ($user, $executionId) {
    return true; // All authenticated users can listen
});

Broadcast::channel('task.{taskId}', function ($user, $taskId) {
    $task = Task::find($taskId);
    return $task && $task->user_id === $user->id;
});

Broadcast::channel('analysis.{taskId}', function ($user, $taskId) {
    $task = Task::find($taskId);
    return $task && $task->user_id === $user->id;
});
