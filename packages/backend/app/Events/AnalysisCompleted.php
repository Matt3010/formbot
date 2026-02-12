<?php

namespace App\Events;

use Illuminate\Broadcasting\InteractsWithSockets;
use Illuminate\Broadcasting\PrivateChannel;
use Illuminate\Contracts\Broadcasting\ShouldBroadcastNow;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class AnalysisCompleted implements ShouldBroadcastNow
{
    use Dispatchable, InteractsWithSockets, SerializesModels;

    public function __construct(
        public string $analysisId,
        public int $userId,
        public array $result,
        public ?string $error = null,
    ) {}

    public function broadcastOn(): array
    {
        return [
            new PrivateChannel('analysis.' . $this->analysisId),
        ];
    }

    public function broadcastAs(): string
    {
        return 'AnalysisCompleted';
    }

    public function broadcastWith(): array
    {
        return [
            'analysis_id' => $this->analysisId,
            'result' => $this->result,
            'error' => $this->error,
        ];
    }
}
