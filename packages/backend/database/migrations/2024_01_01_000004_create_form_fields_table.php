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
        Schema::create('form_fields', function (Blueprint $table) {
            $table->uuid('id')->primary();
            $table->uuid('form_definition_id');
            $table->string('field_name', 255);
            $table->string('field_type', 50);
            $table->text('field_selector');
            $table->string('field_purpose', 100)->nullable();
            $table->text('preset_value')->nullable();
            $table->boolean('is_sensitive')->default(false);
            $table->boolean('is_file_upload')->default(false);
            $table->boolean('is_required')->default(false);
            $table->json('options')->nullable();
            $table->integer('sort_order')->default(0);
            $table->timestamps();

            $table->foreign('form_definition_id')->references('id')->on('form_definitions')->cascadeOnDelete();
        });
    }

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {
        Schema::dropIfExists('form_fields');
    }
};
