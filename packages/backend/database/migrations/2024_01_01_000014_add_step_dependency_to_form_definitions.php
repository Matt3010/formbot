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
        if (Schema::hasColumn('form_definitions', 'depends_on_step_order')) {
            return;
        }

        Schema::table('form_definitions', function (Blueprint $table) {
            $table->integer('depends_on_step_order')->nullable()->after('step_order');
            $table->index('depends_on_step_order');
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        if (!Schema::hasColumn('form_definitions', 'depends_on_step_order')) {
            return;
        }

        Schema::table('form_definitions', function (Blueprint $table) {
            $table->dropIndex(['depends_on_step_order']);
            $table->dropColumn('depends_on_step_order');
        });
    }
};
