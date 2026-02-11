<?php

namespace App\Http\Resources;

use Illuminate\Http\Request;
use Illuminate\Http\Resources\Json\JsonResource;

class FormFieldResource extends JsonResource
{
    /**
     * Transform the resource into an array.
     */
    public function toArray(Request $request): array
    {
        return [
            'id' => $this->id,
            'form_definition_id' => $this->form_definition_id,
            'field_name' => $this->field_name,
            'field_type' => $this->field_type,
            'field_selector' => $this->field_selector,
            'field_purpose' => $this->field_purpose,
            'preset_value' => $this->is_sensitive ? '********' : $this->preset_value,
            'is_sensitive' => $this->is_sensitive,
            'is_file_upload' => $this->is_file_upload,
            'is_required' => $this->is_required,
            'options' => $this->options,
            'sort_order' => $this->sort_order,
            'created_at' => $this->created_at?->toISOString(),
            'updated_at' => $this->updated_at?->toISOString(),
        ];
    }
}
