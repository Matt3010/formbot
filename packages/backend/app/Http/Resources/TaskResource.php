<?php

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

class TaskResource extends JsonResource
{
    /**
     * Transform the resource into an array.
     */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'user_id' => $this->user_id,
            'name' => $this->name,
            'target_url' => $this->target_url,
            'schedule_type' => $this->schedule_type,
            'schedule_cron' => $this->schedule_cron,
            'schedule_at' => $this->schedule_at?->toISOString(),
            'status' => $this->status,
            'is_dry_run' => $this->is_dry_run,
            'max_retries' => $this->max_retries,
            'max_parallel' => $this->max_parallel,
            'stealth_enabled' => $this->stealth_enabled,
            'custom_user_agent' => $this->custom_user_agent,
            'action_delay_ms' => $this->action_delay_ms,
            'cloned_from' => $this->cloned_from,
            'requires_login' => $this->requires_login,
            'login_url' => $this->login_url,
            'login_every_time' => $this->login_every_time,
            'form_definitions' => FormDefinitionResource::collection($this->whenLoaded('formDefinitions')),
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
