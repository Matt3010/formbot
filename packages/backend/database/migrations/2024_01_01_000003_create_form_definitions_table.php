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
        Schema::create('form_definitions', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->uuid('task_id');
            $table->integer('step_order');
            $table->text('page_url');
            $table->enum('form_type', ['login', 'intermediate', 'target']);
            $table->text('form_selector');
            $table->text('submit_selector');
            $table->decimal('ai_confidence', 3, 2)->nullable();
            $table->boolean('captcha_detected')->default(false);
            $table->timestamps();

            $table->unique('id');
            $table->foreign('task_id')->references('id')->on('tasks')->cascadeOnDelete();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('form_definitions');
    }
};
