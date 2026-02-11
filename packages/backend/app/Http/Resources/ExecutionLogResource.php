<?php

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

class ExecutionLogResource extends JsonResource
{
    /**
     * Transform the resource into an array.
     */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'task_id' => $this->task_id,
            'started_at' => $this->started_at?->toISOString(),
            'completed_at' => $this->completed_at?->toISOString(),
            'status' => $this->status,
            'is_dry_run' => $this->is_dry_run,
            'retry_count' => $this->retry_count,
            'error_message' => $this->error_message,
            'screenshot_path' => $this->screenshot_path ? true : false,
            'steps_log' => $this->steps_log,
            'vnc_session_id' => $this->vnc_session_id,
            'task' => new TaskResource($this->whenLoaded('task')),
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
