<?php

namespace App\Listeners;

use App\Events\TaskStatusChanged;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Support\Facades\Log;

class BroadcastTaskEvents implements ShouldQueue
{
    /**
     * Create the event listener.
     */
    public function __construct()
    {
        //
    }

    /**
     * Handle the event.
     */
    public function handle(TaskStatusChanged $event): void
    {
        Log::info('Task status changed broadcast', [
            'task_id' => $event->task->id,
            'status' => $event->task->status,
            'user_id' => $event->task->user_id,
        ]);
    }
}
