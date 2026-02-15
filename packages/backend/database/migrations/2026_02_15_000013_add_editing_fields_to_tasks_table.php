<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * Run the migrations.
     */
    public function up(): void
    {
        // First, drop the existing status column check constraint and recreate with 'editing'
        DB::statement("ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_status_check");
        DB::statement("ALTER TABLE tasks ADD CONSTRAINT tasks_status_check CHECK (status IN ('editing', 'draft', 'active', 'paused', 'completed', 'failed'))");

        // Update default status to 'editing' for new tasks
        DB::statement("ALTER TABLE tasks ALTER COLUMN status SET DEFAULT 'editing'");

        Schema::table('tasks', function (Blueprint $table) {
            // VNC editing session fields
            $table->text('current_editing_url')->nullable()->after('target_url');
            $table->string('vnc_session_id', 100)->nullable()->after('current_editing_url');

            // Editing workflow state
            $table->enum('editing_status', ['idle', 'active', 'confirmed', 'cancelled'])
                  ->default('idle')
                  ->after('status');
            $table->integer('editing_step')->default(0)->after('editing_status');

            // Draft form definitions during editing
            $table->jsonb('user_corrections')->nullable()->after('editing_step');

            // Session expiry tracking
            $table->timestamp('editing_started_at')->nullable()->after('user_corrections');
            $table->timestamp('editing_expires_at')->nullable()->after('editing_started_at');

            // Index for cleanup queries
            $table->index(['editing_status', 'editing_expires_at'], 'idx_editing_cleanup');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::table('tasks', function (Blueprint $table) {
            $table->dropIndex('idx_editing_cleanup');
            $table->dropColumn([
                'current_editing_url',
                'vnc_session_id',
                'editing_status',
                'editing_step',
                'user_corrections',
                'editing_started_at',
                'editing_expires_at',
            ]);
        });

        // Restore original status constraint and default
        DB::statement("ALTER TABLE tasks DROP CONSTRAINT IF EXISTS tasks_status_check");
        DB::statement("ALTER TABLE tasks ADD CONSTRAINT tasks_status_check CHECK (status IN ('draft', 'active', 'paused', 'completed', 'failed'))");
        DB::statement("ALTER TABLE tasks ALTER COLUMN status SET DEFAULT 'draft'");
    }
};
