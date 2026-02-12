<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    public function up(): void
    {
        // Add 'editing' to the status enum
        DB::statement("ALTER TABLE analyses DROP CONSTRAINT IF EXISTS analyses_status_check");
        DB::statement("ALTER TABLE analyses ADD CONSTRAINT analyses_status_check CHECK (status::text = ANY (ARRAY['pending'::text, 'analyzing'::text, 'completed'::text, 'failed'::text, 'cancelled'::text, 'timed_out'::text, 'editing'::text]))");

        Schema::table('analyses', function (Blueprint $table) {
            $table->string('vnc_session_id', 255)->nullable()->after('task_id');
            $table->string('editing_status', 20)->default('idle')->after('vnc_session_id');
            $table->integer('editing_step')->default(0)->after('editing_status');
            $table->jsonb('user_corrections')->nullable()->after('editing_step');
            $table->timestamp('editing_started_at')->nullable()->after('user_corrections');
            $table->timestamp('editing_expires_at')->nullable()->after('editing_started_at');
        });
    }

    public function down(): void
    {
        Schema::table('analyses', function (Blueprint $table) {
            $table->dropColumn([
                'vnc_session_id',
                'editing_status',
                'editing_step',
                'user_corrections',
                'editing_started_at',
                'editing_expires_at',
            ]);
        });

        // Revert status enum
        DB::statement("ALTER TABLE analyses DROP CONSTRAINT IF EXISTS analyses_status_check");
        DB::statement("ALTER TABLE analyses ADD CONSTRAINT analyses_status_check CHECK (status::text = ANY (ARRAY['pending'::text, 'analyzing'::text, 'completed'::text, 'failed'::text, 'cancelled'::text, 'timed_out'::text]))");
    }
};
