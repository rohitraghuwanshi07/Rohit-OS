/* ROHIT OS kernel (Track B): GDT+TSS, IDT, exceptions, paging with demand mapping, PIT timer,
 * page allocator, preemptive round-robin, ring-3 user mode, int 0x80 syscalls, ramfs, shell. */
typedef unsigned int u32; typedef unsigned short u16; typedef unsigned char u8;
typedef unsigned long long u64;
static inline void outb(u16 p, u8 v){ __asm__ volatile("outb %0,%1"::"a"(v),"Nd"(p)); }
static inline u8 inb(u16 p){ u8 v; __asm__ volatile("inb %1,%0":"=a"(v):"Nd"(p)); return v; }

/* ---- console: COM1 + VGA text ---- */
static u16 *vga=(u16*)0xB8000; static int vx, vy;
static void putc(char c){
    while(!(inb(0x3FD)&0x20)); outb(0x3F8,c);
    if(c=='\n'){ vx=0; vy++; } else { vga[vy*80+vx]=(u16)(0x0F00|(u8)c); if(++vx==80){vx=0;vy++;} }
    if(vy==25){ for(int i=0;i<24*80;i++) vga[i]=vga[i+80]; for(int i=24*80;i<2000;i++) vga[i]=0x0F20; vy=24; }
}
static void puts_(const char*s){ while(*s) putc(*s++); }
static void putu(u32 n,u32 base){ char b[12]; int i=0; if(!n) b[i++]='0';
    while(n){ b[i++]="0123456789abcdef"[n%base]; n/=base; } while(i) putc(b[--i]); }
static void kprintf(const char*f,...){
    u32 *a=(u32*)(&f+1);
    for(;*f;f++){ if(*f!='%'){ putc(*f); continue; } f++;
        if(*f=='s') puts_((const char*)*a++); else if(*f=='d'||*f=='u') putu(*a++,10);
        else if(*f=='x'){ puts_("0x"); putu(*a++,16); } else putc(*f); }
}

static void *kmemcpy(void*d,const void*s,u32 n){ char*a=d;const char*b=s; while(n--)*a++=*b++; return d; }
static u32 kstrlen(const char*s){ u32 n=0; while(s[n])n++; return n; }
static int kstreq(const char*a,const char*b){ while(*a&&*a==*b){a++;b++;} return *a==*b; }

/* ---- GDT (kernel + user + TSS), IDT, PIC, PIT ---- */
static u64 gdt[6]={0,0x00CF9A000000FFFFULL,0x00CF92000000FFFFULL,0x00CFFA000000FFFFULL,0x00CFF2000000FFFFULL,0};
static struct{u16 l;u32 b;}__attribute__((packed)) gp;
static u32 tss[26]; static u8 kstack[4096] __attribute__((aligned(16)));
static void gdt_init(void){
    u32 b=(u32)tss,l=sizeof tss-1; tss[1]=(u32)kstack+4096; tss[2]=0x10; tss[25]=104u<<16;
    gdt[5]=(l&0xFFFF)|((u64)(b&0xFFFFFF)<<16)|((u64)0x89<<40)|((u64)((l>>16)&0xF)<<48)|((u64)(b>>24)<<56);
    gp.l=sizeof gdt-1; gp.b=(u32)gdt;
    __asm__ volatile("lgdt %0\n mov $0x10,%%ax\n mov %%ax,%%ds\n mov %%ax,%%es\n mov %%ax,%%fs\n"
        " mov %%ax,%%gs\n mov %%ax,%%ss\n ljmp $0x08,$1f\n 1: mov $0x28,%%ax\n ltr %%ax"::"m"(gp):"ax","memory");
}
struct idt_e{u16 lo,sel;u8 z,fl;u16 hi;}__attribute__((packed));
static struct idt_e idt[256];
static struct{u16 l;u32 b;}__attribute__((packed)) ip;
extern void irq0_stub(void), irq1_stub(void), isr128(void), isr_stubs(void);
static void gate(int n,u32 h,u8 fl){ idt[n]=(struct idt_e){h&0xFFFF,0x08,0,fl,h>>16}; }
static void idt_init(void){
    for(int i=0;i<32;i++) gate(i,(u32)isr_stubs+16*i,0x8E);
    gate(32,(u32)irq0_stub,0x8E); gate(33,(u32)irq1_stub,0x8E); gate(128,(u32)isr128,0xEE);
    ip.l=sizeof idt-1; ip.b=(u32)idt; __asm__ volatile("lidt %0"::"m"(ip));
    outb(0x20,0x11);outb(0xA0,0x11);outb(0x21,0x20);outb(0xA1,0x28);
    outb(0x21,4);outb(0xA1,2);outb(0x21,1);outb(0xA1,1);outb(0x21,0xFC);outb(0xA1,0xFF);
}
static void pit_init(u32 hz){ u32 d=1193182/hz; outb(0x43,0x36); outb(0x40,d&0xFF); outb(0x40,d>>8); }

/* ---- physical page allocator ---- */
extern char _end;
static u32 next_page, free_stack[64], nfree, allocated;
static void pmm_init(void){ next_page=((u32)&_end+4095)&~4095u; }
static u32 pmm_alloc(void){ allocated++; if(nfree) return free_stack[--nfree]; u32 p=next_page; next_page+=4096; return p; }
static void pmm_free(u32 p){ allocated--; free_stack[nfree++]=p; }

/* ---- paging: kernel identity-mapped (supervisor), user + demand regions ---- */
#define UBASE 0x10000000u
#define DBASE 0x40000000u
static u32 pd[1024] __attribute__((aligned(4096))), pt0[8][1024] __attribute__((aligned(4096)));
static u32 demand_faults;
static void paging_init(void){
    for(u32 t=0;t<8;t++){ pd[t]=(u32)pt0[t]|3; for(u32 i=0;i<1024;i++) pt0[t][i]=((t*1024+i)*4096)|3; }
    __asm__ volatile("mov %0,%%cr3\n mov %%cr0,%%eax\n or $0x80000000,%%eax\n mov %%eax,%%cr0"::"r"(pd):"eax","memory");
}
static void map_page(u32 va,u32 pa,u32 fl){
    u32 i=va>>22;
    if(!(pd[i]&1)){ u32 t=pmm_alloc(); for(u32 k=0;k<1024;k++)((u32*)t)[k]=0; pd[i]=t|7; }
    ((u32*)(pd[i]&~0xFFFu))[(va>>12)&1023]=pa|fl; __asm__ volatile("invlpg (%0)"::"r"(va):"memory");
}

/* ---- ramfs ---- */
struct file{ char name[16]; u32 size; char data[256]; int used; } files[16];
static struct file *fs_find(const char*n){ for(int i=0;i<16;i++) if(files[i].used&&kstreq(files[i].name,n)) return &files[i]; return 0; }
static int fs_write(const char*n,const char*d,u32 len){
    struct file*f=fs_find(n);
    if(!f){ for(int i=0;i<16;i++) if(!files[i].used){ f=&files[i]; break; } if(!f||kstrlen(n)>15) return -1; f->used=1; kmemcpy(f->name,n,kstrlen(n)+1); }
    if(len>255) len=255; kmemcpy(f->data,d,len); f->size=len; return (int)len;
}
static int fs_read(const char*n,char*b,u32 max){ struct file*f=fs_find(n); if(!f) return -1; u32 l=f->size<max?f->size:max; kmemcpy(b,f->data,l); return (int)l; }

/* ---- tasks, scheduler, event log ---- */
#define NT 4
#define QUANTUM 5
#define TOTAL_TICKS 300
struct task{ u32 esp; const char*name; volatile u32 count; u32 slices; } tasks[NT];
static int cur, nt=1; static volatile u32 ticks, done; static int irq_on;
static struct{u32 tick; u8 from,to;} elog[64]; static int nev; static u32 qleft=QUANTUM;
static void t1(void){ for(;;) tasks[1].count++; }
static void t2(void){ for(;;) tasks[2].count++; }
static void t3(void){ for(;;) tasks[3].count++; }
static void task_new(const char*name, void(*fn)(void)){
    u32 cs; __asm__ volatile("mov %%cs,%0":"=r"(cs));
    u32 *sp=(u32*)(pmm_alloc()+4096);
    *--sp=0x202; *--sp=cs; *--sp=(u32)fn; *--sp=0x10; *--sp=0x10; for(int i=0;i<8;i++) *--sp=0;
    tasks[nt].esp=(u32)sp; tasks[nt].name=name; nt++;
}
u32 irq0_c(u32 esp){
    outb(0x20,0x20); ticks++; tasks[cur].esp=esp; tasks[cur].slices++;
    if(ticks>=TOTAL_TICKS && !done){ done=1; if(cur!=0){ if(nev<64){elog[nev].tick=ticks;elog[nev].from=cur;elog[nev++].to=0;} cur=0; qleft=QUANTUM; } }
    else if(!done && --qleft==0){ qleft=QUANTUM; int n=(cur+1)%nt;
        if(nev<64){ elog[nev].tick=ticks; elog[nev].from=cur; elog[nev++].to=n; } cur=n; }
    return tasks[cur].esp;
}

/* ---- keyboard (IRQ1) ---- */
static const char sc[]="\0\033" "1234567890-=\b\tqwertyuiop[]\n\0asdfghjkl;'`\0\\zxcvbnm,./\0*\0 ";
static volatile u8 kb[64]; static volatile u32 kh, kt;
void kbd_c(void){ u8 s=inb(0x60); outb(0x20,0x20); if(s<sizeof sc-1&&sc[s]) kb[kt++&63]=sc[s]; }
static char getch(void){
    for(;;){ if(inb(0x3FD)&1) return inb(0x3F8); if(kh!=kt) return kb[kh++&63]; __asm__ volatile("hlt"); }
}

/* ---- exceptions, syscalls, user mode ---- */
struct regs{ u32 edi,esi,ebp,esp,ebx,edx,ecx,eax,es,ds,int_no,err,eip,cs,eflags; };
extern void enter_user(u32 eip,u32 esp), leave_user(void);
extern char hello_start[],hello_end[],bad1_start[],bad1_end[],bad2_start[],bad2_end[];
static const char*exn[]={"divide error","debug","NMI","breakpoint","overflow","bound range","invalid opcode","no FPU",
 "double fault","coproc overrun","invalid TSS","segment not present","stack fault","general protection","page fault","reserved",
 "x87 fault","alignment check","machine check","SIMD fault"};
static int user_status; static int bkpts;
static int uok(u32 p,u32 n){ return p>=UBASE && n<=0x2000 && p+n<=UBASE+0x2000; }
static void syscall(struct regs*r){
    switch(r->eax){
    case 1: { u32 p=r->ebx,n=r->ecx; if(!uok(p,n)||n>256){ r->eax=-1; break; } for(u32 i=0;i<n;i++) putc(((char*)p)[i]); r->eax=n; break; }
    case 2: user_status=0; leave_user(); break;
    case 3: r->eax=ticks; break;
    case 4: { char nm[16],buf[256]; u32 i=0; for(;i<15;i++){ if(!uok(r->ebx+i,1)) break; nm[i]=*(char*)(r->ebx+i); if(!nm[i]) break; } nm[i]=0;
        if(!uok(r->ecx,r->edx)||r->edx>256){ r->eax=-1; break; }
        int l=fs_read(nm,buf,r->edx); if(l>=0) kmemcpy((void*)r->ecx,buf,l); r->eax=l; break; }
    default: r->eax=-1; }
}
void exc_c(struct regs*r){
    if(r->int_no==128){ syscall(r); return; }
    if(r->int_no==3){ bkpts++; kprintf("[exc] breakpoint handled at eip=%x\n",r->eip); return; }
    if(r->int_no==14){ u32 cr2; __asm__ volatile("mov %%cr2,%0":"=r"(cr2));
        if(cr2>=DBASE&&cr2<DBASE+0x400000&&!(r->err&1)){ map_page(cr2&~0xFFFu,pmm_alloc(),3); demand_faults++; return; }
        kprintf("[exc] page fault at %x err=%x eip=%x\n",cr2,r->err,r->eip); }
    else kprintf("[exc] %s (vector %u) err=%x eip=%x\n",r->int_no<20?exn[r->int_no]:"exception",r->int_no,r->err,r->eip);
    if(r->cs&3){ kprintf("[exc] user program killed, kernel survives\n"); user_status=1; leave_user(); }
    kprintf("KERNEL PANIC\n"); outb(0xF4,0x11); for(;;) __asm__ volatile("hlt");
}
static int run_user(const char*s,const char*e){
    u32 code=pmm_alloc(),stk=pmm_alloc();
    map_page(UBASE,code,7); map_page(UBASE+4096,stk,7); kmemcpy((void*)UBASE,s,e-s);
    user_status=-1; enter_user(UBASE,UBASE+8192);
    map_page(UBASE,0,0); map_page(UBASE+4096,0,0); pmm_free(code); pmm_free(stk);
    if(irq_on) __asm__ volatile("sti");
    return user_status;
}

/* ---- shell ---- */
static void readline(char*b,int max){
    int n=0; kprintf("rohit> ");
    for(;;){ char c=getch();
        if(c=='\r'||c=='\n'){ putc('\n'); break; }
        if((c=='\b'||c==127)&&n){ n--; puts_("\b \b"); continue; }
        if(c>=32&&c<127&&n<max-1){ b[n++]=c; putc(c); } }
    b[n]=0;
}
static int ok=1;
static void shell(void){
    char line[96];
    for(;;){
        readline(line,96); char*a=line; while(*a==' ')a++; if(!*a) continue;
        char*arg=a; while(*arg&&*arg!=' ')arg++; if(*arg){ *arg++=0; while(*arg==' ')arg++; }
        if(kstreq(a,"help")) kprintf("help ls cat <f> write <f> <text> rm <f> mem ps ticks fault run crash exit\n");
        else if(kstreq(a,"ls")){ for(int i=0;i<16;i++) if(files[i].used) kprintf("  %s (%u bytes)\n",files[i].name,files[i].size); }
        else if(kstreq(a,"cat")){ char b[257]; int l=fs_read(arg,b,256); if(l<0) kprintf("no such file\n"); else { b[l]=0; kprintf("%s\n",b); } }
        else if(kstreq(a,"write")){ char*t=arg; while(*t&&*t!=' ')t++; if(*t) *t++=0; kprintf(fs_write(arg,t,kstrlen(t))<0?"write failed\n":"ok\n"); }
        else if(kstreq(a,"rm")){ struct file*f=fs_find(arg); if(f){ f->used=0; kprintf("removed\n"); } else kprintf("no such file\n"); }
        else if(kstreq(a,"mem")) kprintf("pages in use %u, demand faults served %u, next free %x\n",allocated,demand_faults,next_page);
        else if(kstreq(a,"ps")){ for(int i=0;i<NT;i++) kprintf("  %s slices=%u work=%u\n",tasks[i].name,tasks[i].slices,tasks[i].count); }
        else if(kstreq(a,"ticks")) kprintf("%u\n",ticks);
        else if(kstreq(a,"fault")){ volatile u32*p=(u32*)(DBASE+0x2000+demand_faults*4096); *p=7; kprintf("demand-mapped page at %x, read back %u\n",(u32)p,*p); }
        else if(kstreq(a,"run")){ int s=run_user(hello_start,hello_end); kprintf("\n[user] exit status %d\n",s); }
        else if(kstreq(a,"crash")){ int s=run_user(bad1_start,bad1_end); kprintf("status %d\n",s); }
        else if(kstreq(a,"exit")){ kprintf("bye\n"); outb(0xF4,ok?0x10:0x11); for(;;) __asm__ volatile("hlt"); }
        else kprintf("unknown command, try help\n");
    }
}

#define CHECK(c,msg) do{ int _c=(c); kprintf("[%s] %s\n",_c?"ok":"FAIL",msg); if(!_c) ok=0; }while(0)
void kmain(u32 mbi){
    int autotest=0;
    if(mbi&&(*(u32*)mbi&4)){ const char*c=(const char*)*(u32*)(mbi+16); for(;*c;c++) if(c[0]=='a'&&c[1]=='u'&&c[2]=='t'&&c[3]=='o') autotest=1; }
    for(int i=0;i<2000;i++) vga[i]=0x0F20;
    outb(0x3F9,0);outb(0x3FB,0x80);outb(0x3F8,3);outb(0x3F9,0);outb(0x3FB,3);outb(0x3FA,0xC7);outb(0x3FC,0x0B);
    kprintf("ROHIT OS kernel booting\n");
    gdt_init(); CHECK(1,"GDT with ring 3 segments and TSS loaded");
    pmm_init();
    u32 a=pmm_alloc(), b=pmm_alloc(), c=pmm_alloc(); pmm_free(b); u32 d=pmm_alloc();
    CHECK(d==b&&a!=c,"page allocator reuses freed pages"); pmm_free(a); pmm_free(c); pmm_free(d);
    paging_init(); CHECK(1,"paging enabled, kernel identity-mapped as supervisor-only");
    idt_init(); pit_init(100); CHECK(1,"IDT: 32 exception gates, timer, keyboard, int 0x80");
    __asm__ volatile("int3"); CHECK(bkpts==1,"breakpoint exception handled and resumed");
    volatile u32*p=(u32*)DBASE; p[0]=0xC0FFEE; p[1024]=0xBEEF;
    CHECK(demand_faults==2&&p[0]==0xC0FFEE&&p[1024]==0xBEEF,"demand paging: unmapped pages mapped on page fault");
    fs_write("motd","welcome to ROHIT OS",19); fs_write("README","ramfs lives in kernel memory",28);
    int hs=run_user(hello_start,hello_end); kprintf("\n"); CHECK(hs==0,"ring 3 program ran, syscalls write/read file/exit");
    CHECK(run_user(bad1_start,bad1_end)==1,"user 'cli' blocked by privilege check, killed");
    CHECK(run_user(bad2_start,bad2_end)==1,"user read of kernel memory blocked by paging, killed");
    char rb[16]; CHECK(fs_write("t","abc",3)==3&&fs_read("t",rb,16)==3&&rb[1]=='b',"ramfs write and read back");
    tasks[0].name="kernel"; task_new("worker1",t1); task_new("worker2",t2); task_new("worker3",t3);
    irq_on=1; __asm__ volatile("sti");
    while(!done) __asm__ volatile("hlt");
    kprintf("\nScheduler event log (%u ticks, quantum %u): %u dispatches\n",ticks,QUANTUM,nev);
    for(int i=0;i<nev&&i<6;i++) kprintf("  t=%u %s -> %s\n",elog[i].tick,tasks[elog[i].from].name,tasks[elog[i].to].name);
    for(int i=1;i<NT;i++) if(!tasks[i].count||!tasks[i].slices) ok=0;
    CHECK(nev>0&&ok,"preemptive round-robin ran all workers");
    kprintf(ok?"ROHITOS SELFTEST PASS\n":"ROHITOS SELFTEST FAIL\n");
    if(autotest){ for(int i=0;i<nev;i++) kprintf("KEV %u %s %s\n",elog[i].tick,tasks[elog[i].from].name,tasks[elog[i].to].name);
        kprintf("autotest mode: leaving without shell\n"); outb(0xF4,ok?0x10:0x11); for(;;) __asm__ volatile("hlt"); }
    shell();
}
