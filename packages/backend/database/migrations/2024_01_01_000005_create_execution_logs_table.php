<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        Schema::create('execution_logs', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->uuid('task_id');
            $table->timestamp('started_at')->nullable();
            $table->timestamp('completed_at')->nullable();
            $table->enum('status', [
                'queued',
                'running',
                'waiting_manual',
                'success',
                'failed',
                'captcha_blocked',
                '2fa_required',
                'dry_run_ok',
            ])->default('queued');
            $table->boolean('is_dry_run')->default(false);
            $table->integer('retry_count')->default(0);
            $table->text('error_message')->nullable();
            $table->text('screenshot_path')->nullable();
            $table->jsonb('steps_log')->nullable();
            $table->string('vnc_session_id', 100)->nullable();
            $table->timestamps();

            $table->foreign('task_id')->references('id')->on('tasks')->cascadeOnDelete();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('execution_logs');
    }
};
