<?php

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

class AnalysisResource extends JsonResource
{
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'user_id' => $this->user_id,
            'url' => $this->url,
            'target_url' => $this->target_url,
            'login_url' => $this->login_url,
            'type' => $this->type,
            'status' => $this->status,
            'result' => $this->result,
            'error' => $this->error,
            'model' => $this->model,
            'task_id' => $this->task_id,
            'vnc_session_id' => $this->vnc_session_id,
            'editing_status' => $this->editing_status ?? 'idle',
            'editing_step' => $this->editing_step ?? 0,
            'user_corrections' => $this->user_corrections,
            'editing_started_at' => $this->editing_started_at?->toISOString(),
            'editing_expires_at' => $this->editing_expires_at?->toISOString(),
            'started_at' => $this->started_at?->toISOString(),
            'completed_at' => $this->completed_at?->toISOString(),
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
