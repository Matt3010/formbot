<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class FormDefinition extends Model
{
    use HasFactory, HasUuids;

    /**
     * The primary key type.
     */
    protected $keyType = 'string';

    /**
     * Indicates if the IDs are auto-incrementing.
     */
    public $incrementing = false;

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'task_id',
        'step_order',
        'page_url',
        'form_type',
        'form_selector',
        'submit_selector',
        'ai_confidence',
        'captcha_detected',
        'two_factor_expected',
        'human_breakpoint',
    ];

    /**
     * Get the attributes that should be cast.
     */
    protected function casts(): array
    {
        return [
            'captcha_detected' => 'boolean',
            'two_factor_expected' => 'boolean',
            'human_breakpoint' => 'boolean',
            'ai_confidence' => 'decimal:2',
        ];
    }

    /**
     * Get the task that owns the form definition.
     */
    public function task(): BelongsTo
    {
        return $this->belongsTo(Task::class);
    }

    /**
     * Get the form fields for the form definition.
     */
    public function formFields(): HasMany
    {
        return $this->hasMany(FormField::class);
    }
}
