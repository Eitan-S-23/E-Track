void __disable_irq(void)
{
    __asm volatile ("cpsid i" ::: "memory");
}

void __enable_irq(void)
{
    __asm volatile ("cpsie i" ::: "memory");
}
