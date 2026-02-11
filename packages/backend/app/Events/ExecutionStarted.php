<?php

namespace App\Events;

use App\Models\ExecutionLog;
use Illuminate\Broadcasting\Channel;
use Illuminate\Broadcasting\InteractsWithSockets;
use Illuminate\Broadcasting\PrivateChannel;
use Illuminate\Contracts\Broadcasting\ShouldBroadcast;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class ExecutionStarted implements ShouldBroadcast
{
    use Dispatchable, InteractsWithSockets, SerializesModels;

    /**
     * Create a new event instance.
     */
    public function __construct(
        public ExecutionLog $execution,
    ) {}

    /**
     * Get the channels the event should broadcast on.
     *
     * @return array<int, Channel>
     */
    public function broadcastOn(): array
    {
        return [
            new PrivateChannel('execution.' . $this->execution->id),
            new PrivateChannel('tasks.' . $this->execution->task->user_id),
        ];
    }

    public function broadcastAs(): string
    {
        return 'ExecutionStarted';
    }

    /**
     * Get the data to broadcast.
     */
    public function broadcastWith(): array
    {
        return [
            'id' => $this->execution->id,
            'task_id' => $this->execution->task_id,
            'status' => $this->execution->status,
            'is_dry_run' => $this->execution->is_dry_run,
            'started_at' => $this->execution->started_at?->toISOString(),
        ];
    }
}
