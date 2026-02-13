<?php

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

class FormDefinitionResource extends JsonResource
{
    /**
     * Transform the resource into an array.
     */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'task_id' => $this->task_id,
            'step_order' => $this->step_order,
            'page_url' => $this->page_url,
            'form_type' => $this->form_type,
            'form_selector' => $this->form_selector,
            'submit_selector' => $this->submit_selector,
            'human_breakpoint' => $this->human_breakpoint,
            // Keep both keys for backward compatibility with frontend payloads.
            'fields' => FormFieldResource::collection($this->whenLoaded('formFields')),
            'form_fields' => FormFieldResource::collection($this->whenLoaded('formFields')),
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
