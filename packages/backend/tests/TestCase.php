<?php

namespace Tests;

use Illuminate\Foundation\Testing\TestCase as BaseTestCase;

abstract class TestCase extends BaseTestCase
{
    protected function setUp(): void
    {
        parent::setUp();

        // Ensure Passport OAuth2 keys exist for any test that uses Passport::actingAs().
        // Without this, tests fail if they run before AuthTest (which also generates keys).
        if (!file_exists(storage_path('oauth-private.key'))) {
            $this->artisan('passport:keys', ['--force' => true, '--no-interaction' => true]);
        }
    }

    protected function defineEnvironment($app): void
    {
        $app['config']->set('database.default', 'sqlite');
        $app['config']->set('database.connections.sqlite.database', ':memory:');
    }
}
