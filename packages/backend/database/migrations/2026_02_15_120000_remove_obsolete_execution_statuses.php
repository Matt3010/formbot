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
        // Migrate any existing captcha_blocked or 2fa_required statuses to 'failed'
        DB::table('execution_logs')
            ->whereIn('status', ['captcha_blocked', '2fa_required'])
            ->update(['status' => 'failed']);

        // PostgreSQL requires recreating the enum type to remove values
        if (DB::connection()->getDriverName() === 'pgsql') {
            // First, create a new enum type with the updated values
            DB::statement("
                CREATE TYPE execution_status_new AS ENUM (
                    'queued',
                    'running',
                    'waiting_manual',
                    'success',
                    'failed',
                    'dry_run_ok'
                )
            ");

            // Alter the column to use the new enum type
            DB::statement("
                ALTER TABLE execution_logs
                ALTER COLUMN status TYPE execution_status_new
                USING status::text::execution_status_new
            ");

            // Drop the old enum type
            DB::statement("DROP TYPE execution_status");

            // Rename the new enum type to the original name
            DB::statement("ALTER TYPE execution_status_new RENAME TO execution_status");
        }
        // For SQLite and other databases, no schema change is needed
        // The enum is just a check constraint that already allows the remaining values
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        // PostgreSQL: recreate the enum with the old values
        if (DB::connection()->getDriverName() === 'pgsql') {
            DB::statement("
                CREATE TYPE execution_status_new AS ENUM (
                    'queued',
                    'running',
                    'waiting_manual',
                    'success',
                    'failed',
                    'captcha_blocked',
                    '2fa_required',
                    'dry_run_ok'
                )
            ");

            DB::statement("
                ALTER TABLE execution_logs
                ALTER COLUMN status TYPE execution_status_new
                USING status::text::execution_status_new
            ");

            DB::statement("DROP TYPE execution_status");
            DB::statement("ALTER TYPE execution_status_new RENAME TO execution_status");
        }
        // For SQLite and other databases, no schema change is needed
        // Note: migrated data (captcha_blocked -> failed) is NOT reversed
    }
};
