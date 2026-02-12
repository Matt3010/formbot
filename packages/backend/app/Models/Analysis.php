<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Analysis extends Model
{
    use HasFactory, HasUuids;

    protected $keyType = 'string';

    public $incrementing = false;

    protected $attributes = [
        'status' => 'pending',
    ];

    protected $fillable = [
        'user_id',
        'url',
        'target_url',
        'login_url',
        'type',
        'status',
        'result',
        'error',
        'model',
        'task_id',
        'vnc_session_id',
        'editing_status',
        'editing_step',
        'user_corrections',
        'editing_started_at',
        'editing_expires_at',
        'started_at',
        'completed_at',
    ];

    protected function casts(): array
    {
        return [
            'result' => 'array',
            'user_corrections' => 'array',
            'started_at' => 'datetime',
            'completed_at' => 'datetime',
            'editing_started_at' => 'datetime',
            'editing_expires_at' => 'datetime',
        ];
    }

    public function user(): BelongsTo
    {
        return $this->belongsTo(User::class);
    }

    public function task(): BelongsTo
    {
        return $this->belongsTo(Task::class);
    }
}
