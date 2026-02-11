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
     * The attributes that are mass assignable.
     */
    protected $fillable = [
        'user_id',
        'name',
        'target_url',
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
    ];

    /**
     * Get the attributes that should be cast.
     */
    protected function casts(): array
    {
        return [
            'is_dry_run' => 'boolean',
            'stealth_enabled' => 'boolean',
            'schedule_at' => 'datetime',
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
