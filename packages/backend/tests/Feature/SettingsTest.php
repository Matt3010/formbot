<?php

namespace Tests\Feature;

use App\Models\AppSetting;
use App\Models\User;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Laravel\Passport\Passport;
use Tests\TestCase;

class SettingsTest extends TestCase
{
    use RefreshDatabase;

    private User $user;

    protected function setUp(): void
    {
        parent::setUp();

        $this->user = User::create([
            'name' => 'Test User',
            'email' => 'test@example.com',
            'password' => bcrypt('password123'),
        ]);

        Passport::actingAs($this->user);
    }

    // -----------------------------------------------------------------
    // Get all settings
    // -----------------------------------------------------------------

    public function test_get_all_settings_returns_empty_when_none_exist(): void
    {
        $response = $this->getJson('/api/settings');

        $response->assertStatus(200)
            ->assertJson([]);
    }

    public function test_get_all_settings_returns_key_value_pairs(): void
    {
        AppSetting::set('max_parallel_global', '5');
        AppSetting::set('retention_days', '30');
        AppSetting::set('default_delay', '500');

        $response = $this->getJson('/api/settings');

        $response->assertStatus(200)
            ->assertJsonPath('max_parallel_global', '5')
            ->assertJsonPath('retention_days', '30')
            ->assertJsonPath('default_delay', '500');
    }

    // -----------------------------------------------------------------
    // Update settings
    // -----------------------------------------------------------------

    public function test_update_settings(): void
    {
        $response = $this->putJson('/api/settings', [
            'settings' => [
                ['key' => 'max_parallel_global', 'value' => '10'],
                ['key' => 'retention_days', 'value' => '60'],
            ],
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('max_parallel_global', '10')
            ->assertJsonPath('retention_days', '60');

        // Verify database persistence
        $this->assertEquals('10', AppSetting::get('max_parallel_global'));
        $this->assertEquals('60', AppSetting::get('retention_days'));
    }

    public function test_update_settings_overwrites_existing_values(): void
    {
        AppSetting::set('retention_days', '30');

        $response = $this->putJson('/api/settings', [
            'settings' => [
                ['key' => 'retention_days', 'value' => '90'],
            ],
        ]);

        $response->assertStatus(200)
            ->assertJsonPath('retention_days', '90');

        $this->assertEquals('90', AppSetting::get('retention_days'));
    }

    public function test_update_settings_preserves_unmodified_settings(): void
    {
        AppSetting::set('max_parallel_global', '5');
        AppSetting::set('retention_days', '30');

        // Only update one setting
        $response = $this->putJson('/api/settings', [
            'settings' => [
                ['key' => 'retention_days', 'value' => '90'],
            ],
        ]);

        $response->assertStatus(200);

        // The untouched setting should still be there
        $this->assertEquals('5', AppSetting::get('max_parallel_global'));
        $this->assertEquals('90', AppSetting::get('retention_days'));
    }

    public function test_update_settings_validation_requires_settings_array(): void
    {
        $response = $this->putJson('/api/settings', []);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['settings']);
    }

    public function test_update_settings_validation_requires_key_and_value(): void
    {
        $response = $this->putJson('/api/settings', [
            'settings' => [
                ['key' => 'test'],  // missing value
            ],
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['settings.0.value']);
    }

    public function test_update_settings_validation_requires_string_key(): void
    {
        $response = $this->putJson('/api/settings', [
            'settings' => [
                ['key' => 123, 'value' => 'test'],
            ],
        ]);

        $response->assertStatus(422)
            ->assertJsonValidationErrors(['settings.0.key']);
    }

    // -----------------------------------------------------------------
    // Health check (public endpoint)
    // -----------------------------------------------------------------

    public function test_health_check_is_accessible(): void
    {
        $response = $this->getJson('/api/health');

        // Should return either 200 or 503 depending on actual service status.
        // In testing with SQLite in-memory DB, the database should be connected.
        $response->assertJsonStructure([
            'status',
            'services' => ['database'],
        ]);

        $this->assertContains($response->status(), [200, 503]);
    }
}
