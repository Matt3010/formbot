<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Task extends Model
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
     * The model's default values for attributes.
     */
    protected $attributes = [
        'status' => 'editing',
        'editing_status' => 'idle',
        'editing_step' => 0,
        'requires_login' => false,
        'login_every_time' => true,
    ];

    /**
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'user_id',
        'name',
        'target_url',
        'current_editing_url',
        'vnc_session_id',
        'editing_status',
        'editing_step',
        'user_corrections',
        'editing_started_at',
        'editing_expires_at',
        'schedule_type',
        'schedule_cron',
        'schedule_at',
        'status',
        'is_dry_run',
        'max_retries',
        'max_parallel',
        'stealth_enabled',
        'custom_user_agent',
        'action_delay_ms',
        'cloned_from',
        'requires_login',
        'login_url',
        'login_every_time',
        'login_session_data',
    ];

    /**
     * Get the attributes that should be cast.
     */
    protected function casts(): array
    {
        return [
            'is_dry_run' => 'boolean',
            'stealth_enabled' => 'boolean',
            'requires_login' => 'boolean',
            'login_every_time' => 'boolean',
            'schedule_at' => 'datetime',
            'user_corrections' => 'array',
            'editing_started_at' => 'datetime',
            'editing_expires_at' => 'datetime',
        ];
    }

    /**
     * Get the route key for the model.
     */
    public function getRouteKeyName(): string
    {
        return 'id';
    }

    /**
     * Get the user that owns the task.
     */
    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    /**
     * Get the form definitions for the task.
     */
    public function formDefinitions(): HasMany
    {
        return $this->hasMany(FormDefinition::class);
    }

    /**
     * Get the execution logs for the task.
     */
    public function executionLogs(): HasMany
    {
        return $this->hasMany(ExecutionLog::class);
    }

    /**
     * Get the task this was cloned from.
     */
    public function clonedFrom(): BelongsTo
    {
        return $this->belongsTo(Task::class, 'cloned_from');
    }
}
