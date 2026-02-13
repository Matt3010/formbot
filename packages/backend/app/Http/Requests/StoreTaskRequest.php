<?php

namespace App\Http\Requests;

use Illuminate\Foundation\Http\FormRequest;

class StoreTaskRequest extends FormRequest
{
    /**
     * Determine if the user is authorized to make this request.
     */
    public function authorize(): bool
    {
        return true;
    }

    /**
     * Get the validation rules that apply to the request.
     */
    public function rules(): array
    {
        return [
            'name' => ['required', 'string', 'max:255'],
            'target_url' => ['required', 'url'],
            'schedule_type' => ['sometimes', 'in:once,cron'],
            'schedule_cron' => ['nullable', 'string', 'max:100'],
            'schedule_at' => ['nullable', 'date'],
            'status' => ['sometimes', 'in:draft,active,paused,completed,failed'],
            'is_dry_run' => ['sometimes', 'boolean'],
            'max_retries' => ['sometimes', 'integer', 'min:0', 'max:10'],
            'max_parallel' => ['sometimes', 'integer', 'min:1', 'max:10'],
            'stealth_enabled' => ['sometimes', 'boolean'],
            'custom_user_agent' => ['nullable', 'string'],
            'action_delay_ms' => ['sometimes', 'integer', 'min:0', 'max:30000'],
            'requires_login' => ['sometimes', 'boolean'],
            'login_url' => ['nullable', 'url', 'required_if:requires_login,true'],
            'login_every_time' => ['sometimes', 'boolean'],

            // Nested form definitions
            'form_definitions' => ['sometimes', 'array'],
            'form_definitions.*.step_order' => ['required_with:form_definitions', 'integer'],
            'form_definitions.*.page_url' => ['required_with:form_definitions', 'string'],
            'form_definitions.*.form_type' => ['required_with:form_definitions', 'in:login,intermediate,target'],
            'form_definitions.*.form_selector' => ['nullable', 'string'],
            'form_definitions.*.submit_selector' => ['nullable', 'string'],
            'form_definitions.*.ai_confidence' => ['nullable', 'numeric', 'min:0', 'max:1'],
            'form_definitions.*.captcha_detected' => ['sometimes', 'boolean'],
            'form_definitions.*.two_factor_expected' => ['sometimes', 'boolean'],

            // Nested form fields
            'form_definitions.*.form_fields' => ['sometimes', 'array'],
            'form_definitions.*.form_fields.*.field_name' => ['required', 'string', 'max:255'],
            'form_definitions.*.form_fields.*.field_type' => ['required', 'string', 'max:50'],
            'form_definitions.*.form_fields.*.field_selector' => ['required', 'string'],
            'form_definitions.*.form_fields.*.field_purpose' => ['nullable', 'string', 'max:100'],
            'form_definitions.*.form_fields.*.preset_value' => ['nullable', 'string'],
            'form_definitions.*.form_fields.*.is_sensitive' => ['sometimes', 'boolean'],
            'form_definitions.*.form_fields.*.is_file_upload' => ['sometimes', 'boolean'],
            'form_definitions.*.form_fields.*.is_required' => ['sometimes', 'boolean'],
            'form_definitions.*.form_fields.*.options' => ['nullable', 'array'],
            'form_definitions.*.form_fields.*.sort_order' => ['sometimes', 'integer'],
        ];
    }
}
