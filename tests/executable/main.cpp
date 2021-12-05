// to compile
// `cmake .`
// `cmake --build .`

#include <iostream>
#include <thread>
#include <array>
#include <chrono>

#define ITERATIONS std::size_t(200)
#define THREADS 32

unsigned int hash(unsigned int x)
{
   return (((x ^ 0xf7f7f7f7) * 0x8364abf7) ^ 0xf00bf00b) * 0xf81bc437;
}
// https://www.random.org/integer-sets/
unsigned int hash_seed[THREADS] = {
	1342, 1656, 1935, 2100, 2653, 2866, 2933, 3322, 3327, 3868, 4050, 4132, 4290, 4996, 5365, 5513, 5557, 5679, 6263, 6528, 6624, 7198, 7685, 7692, 7954, 7988, 8108, 8187, 8344, 8691, 9397, 9616
};

void thread_func(std::size_t ti)
{
	std::this_thread::sleep_for(std::chrono::milliseconds(500));
	const int so = '+';
	const int se = '-';
	unsigned int h = hash_seed[ti];

	for(std::size_t i = 0; i < ITERATIONS;i++)
	{
		h = hash(h + hash_seed[(i + ti) % THREADS]);

		if (h % 2)
			std::fputc(so, stdout);
		else
			std::fputc(se, stderr);

		h = hash(h);

		if ((h % 100) < 10)
		{
			switch(h % 3)
			{
				case 0:
					std::fflush(stdout);
					break;
				case 1:
					std::fflush(stderr);
					break;
				case 2:
					std::this_thread::sleep_for(std::chrono::milliseconds(1000));
					break;
			}
		}
		
	}
}

bool test_seq()
{
#if 0
	std::array<unsigned int,THREADS> hl;
	for(std::size_t ti = 0; ti < THREADS; ti++)
		hl[ti] = hash_seed[ti];
	for(std::size_t i = 0; i < ITERATIONS; i++)
	{
		for(std::size_t ti = 0; ti < THREADS; ti++)
		{
			auto& h = hl[ti];

			h = hash(h + hash_seed[(i + ti) % THREADS]);
			if (h % 2)
				std::cout<<"+";
			else
				std::cout<<"-";
			h = hash(h);
			if ((h % 100) < 10)
			{
				std::cout<<h % 3;
			}
			else
			{
				std::cout<<" ";
			}
		}
		std::cout << std::endl;
	}
	return true;
#else
	return false;
#endif
}

int main()
{
	if(test_seq())
		return 0;

	std::setvbuf(stdout, nullptr, _IONBF, 4);
	std::setvbuf(stderr, nullptr, _IONBF, 4);

	std::array<std::thread,THREADS> l;

	for(std::size_t ti = 0; ti < l.size();ti++)
	{
		std::thread nt([=](){
			thread_func(ti);
		});
		nt.swap(l[ti]);
	}
	for(auto& t : l)
		t.join();

	std::fflush(stdout);
	std::fflush(stderr);

	return 13;
}