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
        // Drop the analyses table completely
        // All VNC editing functionality is now integrated into the tasks table
        Schema::dropIfExists('analyses');
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        // Recreating the analyses table for rollback
        // Note: This will not restore any data that existed before the migration
        Schema::create('analyses', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->foreignId('user_id')->constrained('users')->cascadeOnDelete();
            $table->text('url');
            $table->enum('status', ['pending', 'in_progress', 'completed', 'failed', 'cancelled'])->default('pending');
            $table->jsonb('screenshot_stats')->nullable();
            $table->text('error_message')->nullable();
            $table->timestamps();

            // VNC editing fields
            $table->string('vnc_session_id', 100)->nullable();
            $table->text('current_url')->nullable();
            $table->enum('editing_status', ['idle', 'active', 'confirmed', 'cancelled'])->default('idle');
            $table->integer('current_step')->default(0);
            $table->jsonb('user_corrections')->nullable();
            $table->timestamp('vnc_expires_at')->nullable();
            $table->enum('type', ['automatic', 'manual'])->default('automatic');

            $table->index('user_id');
            $table->index('status');
            $table->index(['editing_status', 'vnc_expires_at']);
        });
    }
};
