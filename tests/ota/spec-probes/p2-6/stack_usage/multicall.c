/* 第二调用点：真实 OTA 代码里 verify/hash 常被多处调用（apply、dry-run、
 * resume 各一次），gcc 因此不一定内联。单一调用点的探针会掩盖
 * 「插桩使父函数栈帧变小」这个机制，故补一个多调用点构型。 */
extern int ota_apply(unsigned nblk);
extern int ota_dry_run(unsigned nblk);
extern volatile unsigned int sink;

int main(void)
{
    int a = ota_apply(4);
    int b = ota_dry_run(2);
    sink += (unsigned)(a + b);
    return a + b;
}
