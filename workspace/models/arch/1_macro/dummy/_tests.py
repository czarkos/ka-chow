import sys
import os

# fmt: off
THIS_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MACRO_NAME = os.path.basename(THIS_SCRIPT_DIR)
sys.path.append(os.path.abspath(os.path.join(THIS_SCRIPT_DIR, '..', '..', '..', '..')))
from scripts import utils as utl
import scripts
# fmt: on


def test_energy_breakdown():
    """
    This test replicates the results presented in Table III of the Albireo
    paper. We show the energy the MRR, MZM, Laser, TIA, DAC, ADC, and Cache.
    Results are shown assuming three levels of future technology scaling:
    conservative (high energy), moderate (medium energy), and aggressive (low
    energy).

    Albireo's energy primarily is consumed by DACs and MRRs. High MRR energy is
    because Albireo uses a large array of MRRs. High DAC energy is because
    Albireo requires many DAC converts for weights because analog-electrical
    weights are only reused for 5 MACs each (low MACs/convert, see the RAELLA
    paper Titanium law).
    """
    results = utl.parallel_test(
        utl.delayed(utl.quick_run)(
            macro=MACRO_NAME
            # variables=dict(
            #     SCALING=f'"{s}"',
            #     # Albireo authors kept the frequency constant for this specific
            #     # table.
            #     GLOBAL_CYCLE_SECONDS=0.2e-9,
            # ),
        )
        for s in ["conservative"]
    )

    def w2pj(*args):  # * 97GHz * 1e15 J->fJ
        return [y * 0.01030927e-9 * 1e15 for y in args]

    # results.consolidate_energy()
    results.add_compare_ref_energy("laser", w2pj(3.88 * 1e-6))
    results.add_compare_ref_energy("photodetector", w2pj(3.88 * 1e-6))
    results.add_compare_ref_energy("individual_modulator_placeholder", w2pj(3.88 * 1e-6))
    results.add_compare_ref_energy("weight_modulators", w2pj(3.88 * 1e-6))
    results.add_compare_ref_energy("adc", w2pj(0.075))
    results.consolidate_energy(["input_dac", "weight_dacs"], "dac")
    results.add_compare_ref_energy("dac", w2pj(0.077))
    results.add_compare_ref_energy("memory_controller", w2pj(0.0186))
    results.add_compare_ref_energy("packet_io", w2pj(0.009))

    return results


def test_area_breakdown():
    """
    This test replicates the results presented in Fig 9 of the Albireo paper. We
    show the area the MRR, MZM, Laser, TIA, DAC, ADC, AWG, and Cache.

    Albireo's area is dominated by large optical-analog interconnects: AWGs and
    star couplers.
    """
    results = utl.single_test(utl.quick_run(macro=MACRO_NAME))

    total_area = 2095.787 * 1000000  # um^2
    expected_area = {
        "Packet I/O": 0.00009876957916047766 * total_area,
        "Memory Controller": 0.03549979077072240642 * total_area,
        "DAC": 0.16604740844370157845 * total_area,
        "ADC": 0.00664189633774806313 * total_area,
        "input_modulator": 0.02862886352477613421 * total_area,
        "weight_modulator": 0.68709272459462722118 * total_area,
        "Photodetector": 0.00000036644945311713 * total_area,
        "Laser": 0.00000477147725412935 * total_area
    }

    results.consolidate_area(["packet_io"], "Packet I/O")
    results.add_compare_ref_area("Packet I/O", [expected_area["Packet I/O"]])
    results.consolidate_area(["memory_controller"], "Memory Controller")
    results.add_compare_ref_area("Memory Controller", [expected_area["Memory Controller"]])
    results.consolidate_area(["weight_dacs", "input_dac"], "DAC")
    results.add_compare_ref_area("DAC", [expected_area["DAC"]])
    results.consolidate_area(["adc"], "ADC")
    results.add_compare_ref_area("ADC", [expected_area["ADC"]])
    results.consolidate_area(["weight_modulators"], "weight_modulator")
    results.add_compare_ref_area("weight_modulator", [expected_area["weight_modulator"]])
    results.consolidate_area(["individual_modulator_placeholder"], "input_modulator")
    results.add_compare_ref_area("input_modulator", [expected_area["input_modulator"]])
    results.consolidate_area(["photodetector"], "Photodetector")
    results.add_compare_ref_area("Photodetector", [expected_area["Photodetector"]])
    results.consolidate_area(["laser"], "Laser")
    results.add_compare_ref_area("Laser", [expected_area["Laser"]])

    results.clear_zero_areas()
    return results


def test_explore_architectures(dnn_name: str):
    """
    ### Architectural Exploration

    In this test, we explore how architecture-level decisions can affect the
    energy efficiency and throughput of the accelerator. One important concept
    to consider when designing mixed-signal accelerators is the amount of reuse
    that the accelerator leverages in the analog-optical, analog-electrical,
    digital-optical, digital-electrical domains. More reuse within a domain
    permits fewer crossings between domains, which can reduce the energy and
    area spent on data converters.

    In this test, we vary:

    - The number of PLCGs in the accelerator. Analog-optical inputs are reused
      between PLCGs, so increasing the number of PLCGs can decrease input
      conversion energy.
    - The number of PLCUs in the accelerator. Analog-electrical outputs are
      reused between PLCUs, so increasing the number of PLCUs can decrease
      output conversion energy.
    - The MRR toplogy. Albireo's MRR array can process up to 15 MACs using a
      convolutional sliding window with 7 inputs, 5 weights, and 5 outputs. This
      topology is often underutilized (because it is optimized only for
      convolutional layers with a stride of 1), so we try a different structure
      with 7 inputs, 3 weights, and 7 outputs. This new structure does not rely
      on convolutional sliding windows to be fully utilized, so it can achieve
      consistently-high utilization across many more layer shapes. It also has
      greater analog-optical weight reuse because every analog-optical weight is
      used for 7 MACs rather than 5, which permits fewer weight conversions (and
      therefore less weight conversion energy). As a tradeoff, the new structure
      has less analog-optical input and analog-optical output reuse, which can
      increase the number (and therefore energy) of input and output conversion.

    We find that increasing the number of PLCGs and PLCUs can increase energy
    efficiency through increased reuse. The new MRR topology decreases weight
    conversion energy and increases utilization, but increases input and output
    conversion energy. Overall, it increases energy efficiency.

    The new MRR topology has higher compute density due to the higher
    utilization. Larger architectures (more PLCUs and PLCGs) generally have
    lower compute density because some layers do not fully utilize them.
    """
    dnn_dir = utl.path_from_model_dir(f"workloads/{dnn_name}")
    layer_paths = [
        os.path.join(dnn_dir, l) for l in os.listdir(dnn_dir) if l.endswith(".yaml")
    ]

    layer_paths = [l for l in layer_paths if "From einsum" not in open(l, "r").read()]

    def callfunc(spec):  # Speed up the test by reducing the victory condition
        spec.mapper.victory_condition = 10

    results = utl.parallel_test(
        utl.delayed(utl.run_layer)(
            macro=MACRO_NAME,
            layer=l,
            variables=dict(
                SCALING=f'"{s}"',
                N_COLUMNS=x,
                N_ROWS=y,
                N_STAR_COUPLED_GROUPS_OF_ROWS=z,
                GLB_DEPTH_SCALE=g,
                N_PLCU=n_plcu,
                N_PLCG=n_plcg,
            ),
            system="ws_dummy_buffer_one_macro",
            callfunc=callfunc,
        )
        for l in layer_paths
        for s in ["aggressive"]
        for x, y, z in [(5, 3, 3), (7, 3, 1)]
        for g in [1]
        for n_plcu in [3, 9, 15]
        for n_plcg in [9, 27, 45]
    )

    results.consolidate_energy(
        ["weight_mach_zehnder_modulator", "weight_dac", "weight_cache"],
        "Weight Processing",
    )
    results.consolidate_energy(
        ["input_mach_zehnder_modulator", "input_dac", "input_MRR"],
        "Input Processing",
    )
    results.consolidate_energy(["adc", "output_regs", "TIA"], "Output Processing")
    results.consolidate_energy(["laser", "MRR", "global_buffer"], "Other")
    results.clear_zero_energies()
    return results.aggregate_by("N_COLUMNS", "N_PLCU", "N_PLCG")


def test_full_dnn(dnn_name: str):
    """
    ### Full-DNN Energy Efficiency and Throughput

    This test explores the throughput and energy efficiency of the accelerator
    for different DNN layers and batch sizes. Looking at the results for the
    batch size of 1, we can see the following:

    - Albireo has low throughput for the fully-connected layers of all DNNs
      (last three layers of AlexNet, last two layers of VGG16, and last layer of
      ResNet18). This is because Albireo is optimized for convolutional layers
      and is underutilized when running fully-connected layers. This being said,
      if we look at the total latency and energy of each layer, we can see that
      fully-connected layers are not significant contributors to the overall
      energy and latency for VGG16 and ResNet18, so this underutilization has a
      smaller impact. However, for AlexNet, the fully-connected layers are
      significant contributors to the overall energy and latency, so this
      underutilization has a larger impact.
    - VGG16 has consistently high throughput for convolutional layers. This is
      because VGG16 uses large weight tensors and convolutional strides of one,
      which allows Albireo to achieve high utilization.
    - AlexNet and ResNet18 have lower throughput for convolutional layers. This
      is due to two factors. First, they often use convolutional strides larger
      than one, for which Albireo is not optimized and becomes underutilized.
      Second, their weight tensor sizes vary more than do those of VGG16, and
      small weight tensors sometimes results in underutilization. These effects
      can be seen especially in ResNet18 layers 7, 12, and 17, which have
      one-wide convolutional filters (R=S=1) that result in severe
      underutilization.

    We can also see that throughput and energy efficiency are correlated because
    underutilization both decreases throughput and increases energy. Energy
    efficiency generally varies less than does throughput because
    underutilization results in fewer activations of some componoents, which can
    somewhat offset the increased energy due to underutilization.

    The batch size of 8 shows similar trends, but the effect of underutilization
    is not as severe because we can increase utilization in some cases by
    running multiple inputs in parallel.

    We note that observing per-layer breakdowns in this way can be a valuable
    tool to understand what causes energy and/or throughput differences across
    full DNNs.
    """
    dnn_dir = utl.path_from_model_dir(f"workloads/{dnn_name}")
    layer_paths = [
        os.path.join(dnn_dir, l) for l in os.listdir(dnn_dir) if l.endswith(".yaml")
    ]

    def callfunc(spec):  # Speed up the test by reducing the victory condition
        spec.mapper.victory_condition = 10

    results = utl.parallel_test(
        utl.delayed(utl.run_layer)(
            macro=MACRO_NAME,
            layer=l,
            variables=dict(
                BATCH_SIZE=n,
                SCALING=f'"{s}"',
            ),
            system="ws_dummy_buffer_one_macro",
            callfunc=callfunc,
        )
        for s in ["conservative"]
        for n in [1, 8]
        for l in layer_paths
    )
    return results


def test_explore_main_memory(dnn_name: str):
    """
    ### Energy Efficiency of Accelerator + Main Memory

    This test explores how the accelerator's energy efficiency is affected by
    the energy of data fetch from DRAM. It also explores two approaches to
    reduce DRAM energy:

    - Batching, where weights are fetched once and reused for multiple
      input/output samples. As a tradeoff, this increases latency. We test with
      a batch size of 8.
    - Keeping inputs and outputs on-chip in the global buffer between layers
      allows the system to avoid moving them to and from DRAM. As a tradeoff,
      this requires a larger global buffer.

    Results are shown assuming three levels of future technology scaling:
    conservative (high energy), moderate (medium energy), and aggressive (low
    energy).

    We find the following:

    - For the conservatively-scaled accelerator, DRAM energy is not a
      significant contributor to overall system energy.
    - For the aggressively-scaled accelerator, DRAM energy dominates overall
      system energy.
    - Batching and keeping inputs and outputs on-chip can each significantly
      reduce DRAM energy.
    - To realize the benefits of aggressive scaling, it is critical to
      incorporate both strategies.
    """

    dnn_dir = utl.path_from_model_dir(f"workloads/{dnn_name}")
    layer_paths = [
        os.path.join(dnn_dir, l) for l in os.listdir(dnn_dir) if l.endswith(".yaml")
    ]

    layer_paths = [l for l in layer_paths if "From einsum" not in open(l, "r").read()]

    def callfunc(spec):  # Speed up the test by reducing the victory condition
        spec.mapper.victory_condition = 10

    results = utl.parallel_test(
        utl.delayed(utl.run_layer)(
            macro=MACRO_NAME,
            layer=l,
            variables=dict(
                BATCH_SIZE=n,
                SCALING=f'"{s}"',
                GLB_DEPTH_SCALE=g,
                SYSTEM_SETTING=f'"{t}"',
            ),
            system=t,
            callfunc=callfunc,
        )
        for l in layer_paths
        for s in ["conservative", "moderate", "aggressive"]
        for n, t, g in [
            (1, "fetch_all_lpddr4", 1),
            (1, "fetch_weights_lpddr4", 2),
            (8, "fetch_all_lpddr4", 16),
            (8, "fetch_weights_lpddr4", 16),
        ]
    )

    results.consolidate_energy(["main_memory"], "DRAM")
    results.consolidate_energy(
        ["weight_mach_zehnder_modulator", "weight_dac", "weight_cache"],
        "Weight Processing",
    )
    results.consolidate_energy(
        ["input_mach_zehnder_modulator", "input_dac", "input_MRR"],
        "Input Processing",
    )
    results.consolidate_energy(["adc", "output_regs", "TIA"], "Output Processing")
    results.consolidate_energy(["laser", "MRR", "global_buffer"], "Other")
    results.clear_zero_energies()

    return results.aggregate_by(
        "BATCH_SIZE",
        "SCALING",
        "SYSTEM_SETTING",
    )


if __name__ == "__main__":
    test_energy_breakdown()
    test_area_breakdown()
    test_full_dnn("alexnet")
    test_full_dnn("vgg16")
    test_explore_architectures("resnet18")
    test_explore_main_memory("resnet18")
