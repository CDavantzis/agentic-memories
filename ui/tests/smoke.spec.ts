import { test, expect } from '@playwright/test'

test('health page renders', async ({ page }) => {
  await page.goto('/')
  await page.getByText('API Health').waitFor()
  expect(await page.locator('text=API Health').count()).toBeGreaterThan(0)
})

test('navigate to retrieve', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('link', { name: 'Retrieve' }).click()
  await page.getByText('Retrieve').waitFor()
  expect(await page.locator('text=Retrieve').count()).toBeGreaterThan(0)
})


