<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class FormField extends Model
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
        'form_definition_id',
        'field_name',
        'field_type',
        'field_selector',
        'field_purpose',
        'preset_value',
        'is_sensitive',
        'is_file_upload',
        'is_required',
        'options',
        'sort_order',
    ];

    /**
     * Get the attributes that should be cast.
     */
    protected function casts(): array
    {
        return [
            'is_sensitive' => 'boolean',
            'is_file_upload' => 'boolean',
            'is_required' => 'boolean',
            'options' => 'array',
        ];
    }

    /**
     * Get the form definition that owns the form field.
     */
    public function formDefinition(): BelongsTo
    {
        return $this->belongsTo(FormDefinition::class);
    }
}
