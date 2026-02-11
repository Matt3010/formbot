<?php

namespace App\Events;

use App\Models\ExecutionLog;
use Illuminate\Broadcasting\Channel;
use Illuminate\Broadcasting\InteractsWithSockets;
use Illuminate\Broadcasting\PrivateChannel;
use Illuminate\Contracts\Broadcasting\ShouldBroadcast;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class CaptchaDetected implements ShouldBroadcast
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

    /**
     * Get the data to broadcast.
     */
    public function broadcastWith(): array
    {
        return [
            'id' => $this->execution->id,
            'task_id' => $this->execution->task_id,
            'status' => 'captcha_blocked',
            'vnc_session_id' => $this->execution->vnc_session_id,
            'message' => 'CAPTCHA detected. Manual intervention may be required.',
        ];
    }
}
