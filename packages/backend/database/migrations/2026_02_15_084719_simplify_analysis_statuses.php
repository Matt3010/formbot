<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * Run the migrations.
     *
     * This migration simplifies analysis statuses from 7 to 5 by:
     * - Merging 'cancelled' → 'failed' with error message "Cancelled by user"
     * - Merging 'timed_out' → 'failed' with error message "Analysis timed out after 1 hour"
     * - Final statuses: pending, analyzing, completed, failed, editing
     */
    public function up(): void
    {
        // First, migrate existing data
        // Update cancelled analyses to failed with appropriate error message
        DB::table('analyses')
            ->where('status', 'cancelled')
            ->update([
                'status' => 'failed',
                'error' => DB::raw("COALESCE(error, 'Cancelled by user')"),
            ]);

        // Update timed_out analyses to failed with appropriate error message
        DB::table('analyses')
            ->where('status', 'timed_out')
            ->update([
                'status' => 'failed',
                'error' => DB::raw("COALESCE(error, 'Analysis timed out after 1 hour')"),
            ]);

        // Update PostgreSQL constraint to allow only 5 statuses
        if (DB::connection()->getDriverName() === 'pgsql') {
            DB::statement("ALTER TABLE analyses DROP CONSTRAINT IF EXISTS analyses_status_check");
            DB::statement("ALTER TABLE analyses ADD CONSTRAINT analyses_status_check CHECK (status::text = ANY (ARRAY['pending'::text, 'analyzing'::text, 'completed'::text, 'failed'::text, 'editing'::text]))");
        }
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        // Restore PostgreSQL constraint to include cancelled and timed_out
        if (DB::connection()->getDriverName() === 'pgsql') {
            DB::statement("ALTER TABLE analyses DROP CONSTRAINT IF EXISTS analyses_status_check");
            DB::statement("ALTER TABLE analyses ADD CONSTRAINT analyses_status_check CHECK (status::text = ANY (ARRAY['pending'::text, 'analyzing'::text, 'completed'::text, 'failed'::text, 'cancelled'::text, 'timed_out'::text, 'editing'::text]))");
        }

        // Note: We don't reverse the data migration as we can't determine
        // which 'failed' records were originally 'cancelled' or 'timed_out'
    }
};
