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
        Schema::create('tasks', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('user_id')->constrained('users')->cascadeOnDelete();
            $table->string('name', 255);
            $table->text('target_url');
            $table->enum('schedule_type', ['once', 'cron'])->default('once');
            $table->string('schedule_cron', 100)->nullable();
            $table->timestamp('schedule_at')->nullable();
            $table->enum('status', ['draft', 'active', 'paused', 'completed', 'failed'])->default('draft');
            $table->boolean('is_dry_run')->default(false);
            $table->integer('max_retries')->default(3);
            $table->integer('max_parallel')->default(1);
            $table->boolean('stealth_enabled')->default(true);
            $table->text('custom_user_agent')->nullable();
            $table->integer('action_delay_ms')->default(500);
            $table->uuid('cloned_from')->nullable();
            $table->timestamps();

            $table->unique('id');
            $table->foreign('cloned_from')->references('id')->on('tasks')->nullOnDelete();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('tasks');
    }
};
