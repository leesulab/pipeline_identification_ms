#main.py
#-*- coding:utf-8 -*--

import gc 
import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
import warnings
import pandas as pd
from pathlib import Path
from io import StringIO
import sys
import time
from tqdm import tqdm
import matplotlib.pyplot as plt 
from typing import Any, Callable, Dict, List, Optional, Union
import psutil


# Configuration
from scripts.config.config import Config

# Classes pour le traitement
from scripts.processing.peak_detection import PeakDetector
from scripts.processing.blank_processing import BlankProcessor
from scripts.processing.replicate_processing import ReplicateProcessor
from scripts.processing.ccs_calibration import CCSCalibrator
from scripts.processing.identification import CompoundIdentifier
from scripts.processing.feature_matrix import FeatureProcessor
from scripts.utils.replicate_handling import ReplicateHandler


# Utilitaires
from scripts.utils.io_handlers import IOHandler
from scripts.utils.replicate_handling import ReplicateHandler

# Visualisations 
from scripts.visualization.plotting import (
    plot_unique_molecules_per_sample,
    plot_level1_molecules_per_sample,
    plot_sample_similarity_heatmap,
    plot_sample_similarity_heatmap_by_confidence,
    plot_level1_molecule_distribution_bubble,
    analyze_sample_clusters,
    plot_cluster_statistics,
    analyze_and_save_clusters,
    plot_tics_interactive,
    analyze_categories
)

# Suppression des warnings pandas
warnings.filterwarnings('ignore')
pd.options.mode.chained_assignment = None

# Initialiser le logger
logger = logging.getLogger(__name__)

def setup_logging(log_dir: Union[str, Path, None] = None) -> Path:
    """Configure le logging dans le dossier de travail de la pipeline."""
    if log_dir is None:
        log_dir = Config.PATHS.BASE_DIR / "logs"

    log_dir = Path(log_dir).expanduser().resolve()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pipeline.log"

    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True
    )

    return log_file

class CaptureOutput:
    """Capture la sortie standard pour chaque processus."""
    def __init__(self):
        self.output = StringIO()
        self.stdout = sys.stdout
        
    def __enter__(self):
        sys.stdout = self.output
        return self.output
        
    def __exit__(self, *args):
        sys.stdout = self.stdout

class SampleResult:
    """Stocke les résultats du traitement d'un échantillon."""
    def __init__(self, name: str, peaks_df: pd.DataFrame, processing_time: float, logs: str):
        self.name = name
        self.peaks_df = peaks_df
        self.processing_time = processing_time
        self.logs = logs
        self.success = not peaks_df.empty
        
        # Extraire les statistiques des logs
        self.initial_peaks = 0
        self.after_clustering = 0
        self.after_blank = len(peaks_df) if not peaks_df.empty else 0
        self.final_peaks = len(peaks_df) if not peaks_df.empty else 0
        
        for line in logs.split('\n'):
            if "Pics initiaux:" in line:
                try:
                    self.initial_peaks = int(line.split(": ")[1])
                except:
                    pass
            elif "après clustering:" in line and "après clustering: {len" not in line:
                try:
                    self.after_clustering = int(line.split(": ")[1])
                except:
                    pass
            elif "Pics après soustraction" in line:
                try:
                    self.after_blank = int(line.split(": ")[1])
                except:
                    pass

def process_single_sample(
    args: tuple
) -> tuple:
    """Traite un seul échantillon en capturant sa sortie."""
    base_name, replicates, blank_peaks, calibrator, output_base_dir = args
    start_time = time.time()
    
    with CaptureOutput() as output:
        try:
            # Instanciation des processeurs
            replicate_processor = ReplicateProcessor()
            blank_processor = BlankProcessor()
            
            # 1. Traitement des réplicats
            common_peaks = replicate_processor.process_sample_with_replicates(
                base_name,
                replicates,
                output_base_dir
            )
            
            if common_peaks.empty:
                print(f"✗ Pas de pics trouvés pour {base_name}")
                return base_name, SampleResult(
                    base_name, pd.DataFrame(), 
                    time.time() - start_time, 
                    output.getvalue()
                )
            
            # 2. Soustraction du blank 
            if not blank_peaks.empty:
                clean_peaks = blank_processor.subtract_blank_peaks(common_peaks, blank_peaks)
            else:
                clean_peaks = common_peaks
                
            if clean_peaks.empty:
                print(f"✗ Pas de pics après soustraction du blank pour {base_name}")
                return base_name, SampleResult(
                    base_name, pd.DataFrame(), 
                    time.time() - start_time, 
                    output.getvalue()
                )
            
            # 3. Calibration CCS 
            peaks_with_ccs = calibrator.calculate_ccs(clean_peaks)
            
            if not peaks_with_ccs.empty:
                print(f"✓ CCS calculées pour {len(peaks_with_ccs)} pics")
                print(f"✓ Plage de CCS: {peaks_with_ccs['CCS'].min():.2f} - {peaks_with_ccs['CCS'].max():.2f} Å²")
                print(f"✓ CCS moyenne: {peaks_with_ccs['CCS'].mean():.2f} Å²")
                
                # Sauvegarde
                io_handler = IOHandler()
                output_dir = output_base_dir / base_name / "ms1"
                output_dir.mkdir(parents=True, exist_ok=True)
                output_file = output_dir / "common_peaks.parquet"
                io_handler.save_results(peaks_with_ccs, output_file)
                
            return base_name, SampleResult(
                base_name, peaks_with_ccs,
                time.time() - start_time,
                output.getvalue()
            )
            
        except Exception as e:
            print(f"❌ Erreur lors du traitement de {base_name}: {str(e)}")
            return base_name, SampleResult(
                base_name, pd.DataFrame(),
                time.time() - start_time,
                output.getvalue()
            )

def generate_molecules_per_sample(output_dir: Path):
    fig = plot_unique_molecules_per_sample(output_dir)
    fig.savefig(output_dir / "molecules_per_sample.png", bbox_inches='tight', dpi=300)
    plt.close(fig)

def generate_level1_molecules(output_dir: Path):
    fig = plot_level1_molecules_per_sample(output_dir)
    fig.savefig(output_dir / "level1_molecules_per_sample.png", bbox_inches='tight', dpi=300)
    plt.close(fig)

def generate_bubble_plot(output_dir: Path):
    fig = plot_level1_molecule_distribution_bubble(output_dir)
    fig.savefig(output_dir / "level1_molecule_distribution_bubble.png", bbox_inches='tight', dpi=300)
    plt.close(fig)

def generate_similarity_heatmap(output_dir: Path):
    fig = plot_sample_similarity_heatmap(output_dir)
    fig.savefig(output_dir / "sample_similarity_heatmap_all.png", bbox_inches='tight', dpi=300)
    plt.close(fig)

def generate_level1_heatmap(output_dir: Path):
    fig = plot_sample_similarity_heatmap_by_confidence(
        output_dir, 
        confidence_levels=[1],
        title_suffix=" - Niveau 1"
    )
    fig.savefig(output_dir / "sample_similarity_heatmap_level1.png", bbox_inches='tight', dpi=300)
    plt.close(fig)

def generate_level12_heatmap(output_dir: Path):
    fig = plot_sample_similarity_heatmap_by_confidence(
        output_dir, 
        confidence_levels=[1, 2],
        title_suffix=" - Niveaux 1 et 2"
    )
    fig.savefig(output_dir / "sample_similarity_heatmap_level12.png", bbox_inches='tight', dpi=300)
    plt.close(fig)

def generate_level123_heatmap(output_dir: Path):
    fig = plot_sample_similarity_heatmap_by_confidence(
        output_dir, 
        confidence_levels=[1, 2, 3],
        title_suffix=" - Niveaux 1, 2 et 3"
    )
    fig.savefig(output_dir / "sample_similarity_heatmap_level123.png", bbox_inches='tight', dpi=300)
    plt.close(fig)

def generate_tics(output_dir: Path):
    plot_tics_interactive(Path("data/input/samples"), output_dir)

def generate_visualizations(output_dir: Path) -> None:
    """Génère toutes les visualisations de la pipeline en parallèle."""
    try:
        print("\n📊 Génération des visualisations...")
        output_dir.mkdir(exist_ok=True)
        
        # Vérifier l'existence du fichier d'identifications dans le sous-dossier feature_matrix
        identifications_file = output_dir / "feature_matrix" / "features_complete.parquet"
        if not identifications_file.exists():
            raise FileNotFoundError(f"Fichier d'identifications non trouvé: {identifications_file}")

        # Liste des tâches à exécuter avec leurs arguments
        tasks = [
            (generate_molecules_per_sample, output_dir),
            (generate_level1_molecules, output_dir),
            (generate_bubble_plot, output_dir),
            (generate_similarity_heatmap, output_dir),
            (generate_level1_heatmap, output_dir),
            (generate_level12_heatmap, output_dir),
            (generate_level123_heatmap, output_dir)
            #,(generate_tics, output_dir)
        ]

        # Exécution parallèle des tâches
        max_workers = min(mp.cpu_count(), len(tasks))

        futures_to_task = {}
        with ProcessPoolExecutor(max_workers=2) as executor:
            # Soumettre toutes les tâches
            for func, arg in tasks:
                future = executor.submit(func, arg)
                futures_to_task[future] = func.__name__
            
            # Attendre leur complétion avec une barre de progression
            with tqdm(total=len(futures_to_task), desc="Génération des visualisations") as pbar:
                for future in as_completed(futures_to_task):
                    task_name = futures_to_task[future]
                    try:
                        future.result()
                    except Exception as e:
                        print(f"Erreur lors de la génération de {task_name}: {str(e)}")
                    pbar.update(1)

        print(f"   ✓ Visualisations sauvegardées dans {output_dir}")

    except Exception as e:
        print(f"❌ Erreur lors de la création des visualisations: {str(e)}")
        raise

def process_samples_parallel(
    replicate_groups: Dict[str, List[Path]],
    blank_peaks: pd.DataFrame,
    calibrator: CCSCalibrator,
    output_base_dir: Path,
    max_workers: int = None
) -> Dict[str, SampleResult]:
    """
    Traite tous les échantillons en parallèle avec une gestion optimisée de la mémoire.
    
    Args:
        replicate_groups: Dictionnaire des groupes de réplicats
        blank_peaks: DataFrame des pics du blank
        calibrator: Instance du calibrateur CCS
        output_base_dir: Répertoire de sortie
        max_workers: Nombre maximum de workers
        
    Returns:
        Dict[str, SampleResult]: Résultats par échantillon
    """
    if max_workers is None:
        max_workers = min(2, mp.cpu_count())

    total_samples = len(replicate_groups)    
    print("\n" + "="*80)
    print(f"TRAITEMENT DES ÉCHANTILLONS ({total_samples} échantillons)")
    print("="*80)
    
    # Analyse préliminaire des tailles d'échantillons
    print("\nAnalyse des tailles d'échantillons...")
    sample_sizes = {}
    for base_name, replicates in replicate_groups.items():
        total_size = 0
        for rep_file in replicates:
            file_size = rep_file.stat().st_size
            # Estimation de la mémoire nécessaire (facteur 3 pour le traitement)
            memory_needed = file_size * 3
            total_size += memory_needed
        sample_sizes[base_name] = total_size
        print(f"   • {base_name}: {total_size / 1024**2:.1f} MB estimés")
    
    # Calcul de la taille de lot basée sur la mémoire disponible
    available_memory = psutil.virtual_memory().available
    target_memory_usage = available_memory * 0.7  # Utilise 70% de la RAM disponible
    
    # Tri des échantillons par taille
    sorted_samples = sorted(sample_sizes.items(), key=lambda x: x[1], reverse=True)
    
    # Création de lots équilibrés
    batches = []
    current_batch = []
    current_batch_size = 0
    
    for sample_name, sample_size in sorted_samples:
        if current_batch_size + sample_size > target_memory_usage or len(current_batch) >= max_workers:
            if current_batch:
                batches.append(current_batch)
            current_batch = [(sample_name, replicate_groups[sample_name])]
            current_batch_size = sample_size
        else:
            current_batch.append((sample_name, replicate_groups[sample_name]))
            current_batch_size += sample_size
    
    if current_batch:
        batches.append(current_batch)
    
    print(f"\nOptimisation des ressources:")
    print(f"   • Nombre de lots: {len(batches)}")
    print(f"   • Workers: {max_workers}")
    print(f"   • Mémoire disponible: {available_memory / 1024**3:.1f} GB")
    print(f"   • Utilisation mémoire cible: {target_memory_usage / 1024**3:.1f} GB")
    
    results = {}
    total_start_time = time.time()
    process = psutil.Process()
    initial_memory = process.memory_info().rss
    
    with tqdm(total=total_samples, unit="échantillon") as pbar:
        for batch_idx, batch_items in enumerate(batches, 1):
            print(f"\nTraitement du lot {batch_idx}/{len(batches)} "
                  f"({len(batch_items)} échantillons)")
            
            # Force le garbage collector avant chaque batch
            gc.collect()
            
            # Surveillance de la mémoire
            current_memory = process.memory_info().rss
            memory_increase = current_memory - initial_memory
            if memory_increase > 1e9:  # Si augmentation > 1GB
                print("\n⚠️ Forte utilisation mémoire détectée, nettoyage forcé...")
                gc.collect()
                initial_memory = process.memory_info().rss
            
            process_args = [
                (base_name, replicates, blank_peaks, calibrator, output_base_dir)
                for base_name, replicates in batch_items
            ]
            
            try:
                with ProcessPoolExecutor(max_workers=max_workers) as executor:
                    future_to_name = {
                        executor.submit(process_single_sample, args): args[0]
                        for args in process_args
                    }
                    
                    for future in as_completed(future_to_name):
                        base_name = future_to_name[future]
                        try:
                            _, result = future.result()
                            
                            # Sauvegarde immédiate des résultats sur disque si possible
                            if result.success and hasattr(result, 'peaks_df') and not result.peaks_df.empty:
                                output_dir = output_base_dir / base_name / "ms1"
                                output_dir.mkdir(parents=True, exist_ok=True)
                                result.peaks_df.to_parquet(
                                    output_dir / "processed_peaks.parquet",
                                    compression='snappy'
                                )
                                # Libérer la mémoire du DataFrame
                                result.peaks_df = None
                                gc.collect()
                            
                            results[base_name] = result
                            
                        except Exception as e:
                            print(f"\n❌ Erreur pour {base_name}: {str(e)}")
                            results[base_name] = SampleResult(
                                base_name, 
                                pd.DataFrame(), 
                                0.0,
                                f"Erreur: {str(e)}"
                            )
                        finally:
                            pbar.update(1)
                            
                            # Sauvegarde intermédiaire des statistiques
                            stats_df = pd.DataFrame([{
                                'Échantillon': r.name,
                                'Temps (s)': r.processing_time,
                                'Pics initiaux': r.initial_peaks,
                                'Pics après clustering': r.after_clustering,
                                'Pics après blank': r.after_blank,
                                'Pics finaux': r.final_peaks,
                                'Statut': 'Succès' if r.success else 'Échec'
                            } for r in results.values()])
                            
                            stats_file = output_base_dir / "processing_statistics.csv"
                            stats_df.to_csv(stats_file, index=False)
                            del stats_df
                            gc.collect()
                
            except Exception as e:
                print(f"\n❌ Erreur dans le lot {batch_idx}: {str(e)}")
                for name, _ in batch_items:
                    if name not in results:
                        results[name] = SampleResult(
                            name,
                            pd.DataFrame(),
                            0.0,
                            f"Erreur batch: {str(e)}"
                        )
                        pbar.update(1)
            
            # Pause entre les lots pour libération mémoire
            if batch_idx < len(batches):
                #print("\n💤 Pause pour libération mémoire...")
                time.sleep(2)
                gc.collect()
    
    total_time = time.time() - total_start_time
    success_count = sum(1 for r in results.values() if r.success)
    failed_count = len(results) - success_count
    
    # Affichage du récapitulatif
    print("\n" + "="*80)
    print("RÉCAPITULATIF")
    print("="*80)
    print(f"\nTemps total: {total_time:.2f} secondes")
    print(f"Échantillons traités: {success_count}/{len(results)}")
    
    if failed_count > 0:
        print(f"❌ Échantillons en échec: {failed_count}")
    
    print("\nDétails par échantillon:")
    for name, result in results.items():
        status = "✓" if result.success else "✗"
        print(f"\n{status} {name}")
        print(f"  • Temps de traitement: {result.processing_time:.2f}s")
        print(f"  • Pics initiaux: {result.initial_peaks}")
        if result.success:
            print(f"  • Pics après clustering: {result.after_clustering}")
            print(f"  • Pics après blank: {result.after_blank}")
            print(f"  • Pics finaux: {result.final_peaks}")
        else:
            print(f"  • Erreur: {result.logs}")
    
    # Dernière sauvegarde des statistiques
    final_stats_df = pd.DataFrame([{
        'Échantillon': r.name,
        'Temps (s)': r.processing_time,
        'Pics initiaux': r.initial_peaks,
        'Pics après clustering': r.after_clustering,
        'Pics après blank': r.after_blank,
        'Pics finaux': r.final_peaks,
        'Statut': 'Succès' if r.success else 'Échec'
    } for r in results.values()])
    
    stats_file = output_base_dir / "processing_statistics.csv"
    final_stats_df.to_csv(stats_file, index=False)
    
    print(f"\nStatistiques sauvegardées dans {stats_file}")
    
    return results

def save_intermediate_stats(results: Dict[str, SampleResult], output_dir: Path) -> None:
    """Sauvegarde les statistiques intermédiaires."""
    stats_df = pd.DataFrame([{
        'Échantillon': r.name,
        'Temps (s)': r.processing_time,
        'Pics initiaux': r.initial_peaks,
        'Pics après clustering': r.after_clustering,
        'Pics après blank': r.after_blank,
        'Pics finaux': r.final_peaks,
        'Statut': 'Succès' if r.success else 'Échec'
    } for r in results.values()])
    
    stats_file = output_dir / "processing_statistics.csv"
    stats_df.to_csv(stats_file, index=False)
    
def print_final_stats(results: Dict[str, SampleResult]) -> None:
    """Affiche les statistiques finales du traitement."""
    success_count = sum(1 for r in results.values() if r.success)
    failed_count = len(results) - success_count
    
    print("\n" + "="*80)
    print("STATISTIQUES FINALES")
    print("="*80)
    print(f"\n✓ Échantillons traités avec succès: {success_count}")
    if failed_count > 0:
        print(f"✗ Échantillons en échec: {failed_count}")
    
    # Statistiques sur la mémoire
    process = psutil.Process()
    memory_info = process.memory_info()
    print(f"\nUtilisation mémoire finale: {memory_info.rss / 1024**3:.2f} GB")

PIPELINE_STEPS = (
    "calibration",
    "identification",
    "file_discovery",
    "blanks",
    "samples",
    "feature_alignment",
    "visualizations",
    "similarities",
    "categories",
)


def normalize_steps(
    steps: Union[str, List[str], None] = None,
) -> List[str]:
    """Valide et normalise les étapes demandées."""
    if steps is None or steps == "all":
        return list(PIPELINE_STEPS)

    if isinstance(steps, str):
        requested_steps = [steps]
    else:
        requested_steps = list(steps)

    if not requested_steps:
        raise ValueError("Au moins une étape doit être sélectionnée.")

    unknown_steps = sorted(
        set(requested_steps) - set(PIPELINE_STEPS)
    )

    if unknown_steps:
        raise ValueError(
            "Étape(s) inconnue(s) : "
            + ", ".join(unknown_steps)
            + ". Étapes autorisées : "
            + ", ".join(PIPELINE_STEPS)
        )

    return [
        step
        for step in PIPELINE_STEPS
        if step in requested_steps
    ]

def get_blank_peaks_file() -> Path:
    """Retourne le fichier persistant contenant les pics des blanks."""
    return (
        Config.PATHS.INTERMEDIATE_DIR
        / "blanks"
        / "blank_peaks.parquet"
    )


def save_blank_peaks(blank_peaks: pd.DataFrame) -> Path:
    """Sauvegarde les pics des blanks pour une reprise ultérieure."""
    output_file = get_blank_peaks_file()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    blank_peaks.to_parquet(output_file, index=False)
    return output_file


def load_blank_peaks() -> pd.DataFrame:
    """Recharge les pics des blanks produits par une exécution précédente."""
    input_file = get_blank_peaks_file()

    if not input_file.exists():
        raise FileNotFoundError(
            "Résultat persistant des blanks introuvable : "
            f"{input_file}. Exécutez d'abord l'étape 'blanks'."
        )

    return pd.read_parquet(input_file)


def load_optional_blank_peaks(
    blank_files: List[Path],
) -> pd.DataFrame:
    """
    Recharge les blanks persistants pour le traitement des échantillons.

    Si des blanks bruts existent mais n'ont pas encore été traités,
    l'étape samples est refusée afin d'éviter une analyse sans soustraction.
    """
    blank_peaks_file = get_blank_peaks_file()

    if blank_peaks_file.exists():
        return load_blank_peaks()

    if blank_files:
        raise FileNotFoundError(
            "Des fichiers blanks bruts sont présents, mais leur résultat "
            f"traité est absent : {blank_peaks_file}. "
            "Exécutez d'abord l'étape 'blanks'."
        )

    return pd.DataFrame()


def discover_input_files(
    require_samples: bool = True,
) -> Dict[str, Any]:
    """Détecte les blanks et regroupe les réplicats d'échantillons."""
    blank_files = sorted(
        Config.PATHS.INPUT_BLANKS.glob("*.parquet")
    )
    sample_files = sorted(
        Config.PATHS.INPUT_SAMPLES.glob("*.parquet")
    )

    if require_samples and not sample_files:
        raise ValueError(
            "Aucun fichier d'échantillon trouvé dans "
            f"{Config.PATHS.INPUT_SAMPLES}"
        )

    replicate_groups = {}

    if sample_files:
        replicate_handler = ReplicateHandler()
        replicate_groups = replicate_handler.group_replicates(
            sample_files
        )

    return {
        "blank_files": blank_files,
        "sample_files": sample_files,
        "replicate_groups": replicate_groups,
    }


def _emit_progress(
    callback: Optional[Callable[[Dict[str, Any]], None]],
    *,
    step: str,
    status: str,
    message: str,
    progress: Optional[float],
) -> None:
    """Transmet un événement de progression sans dépendre d'une interface."""
    if callback is None:
        return

    event = {
        "step": step,
        "status": status,
        "message": message,
        "progress": progress,
    }

    try:
        callback(event)
    except Exception as callback_error:
        logger.warning(
            "Erreur dans le callback de progression : %s",
            callback_error,
        )


def run_pipeline(
    base_dir: Union[str, Path, None] = None,
    steps: Union[str, List[str], None] = None,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    Exécute la pipeline complète.

    Args:
        base_dir:
            Dossier de travail contenant l'arborescence data/.
            Si aucune valeur n'est fournie, les chemins par défaut de Config
            sont conservés.
        steps:
            Étapes à exécuter. Une valeur absente ou égale à "all"
            sélectionne la pipeline complète.
        progress_callback:
            Fonction optionnelle recevant les événements de progression sous
            forme de dictionnaires.
    """
    selected_steps = normalize_steps(steps)

    if base_dir is not None:
        Config.set_base_dir(base_dir)

    Config.setup_directories()
    log_file = setup_logging()
    start_time = time.time()
    print("\n🚀 DÉMARRAGE DE LA PIPELINE D'ANALYSE")
    print("=" * 80)

    _emit_progress(
        progress_callback,
        step="pipeline",
        status="running",
        message="Démarrage de la pipeline",
        progress=0.0,
    )

    try:
        # Initialisation des handlers et processeurs
        io_handler = IOHandler()
        replicate_handler = ReplicateHandler()
        blank_processor = BlankProcessor()
        feature_processor = FeatureProcessor()

        if selected_steps == ["file_discovery"]:
            _emit_progress(
                progress_callback,
                step="file_discovery",
                status="running",
                message="Détection des fichiers d'entrée",
                progress=0.20,
            )

            discovered = discover_input_files(
                require_samples=False
            )

            blank_files = discovered["blank_files"]
            sample_files = discovered["sample_files"]
            replicate_groups = discovered["replicate_groups"]

            print("\n📁 Détection des fichiers")
            print(f"   • Blanks : {len(blank_files)}")
            print(f"   • Fichiers échantillons : {len(sample_files)}")
            print(
                "   • Groupes d'échantillons : "
                f"{len(replicate_groups)}"
            )

            total_time = time.time() - start_time

            pipeline_result = {
                "status": "success",
                "base_dir": str(Config.PATHS.BASE_DIR),
                "output_dir": str(Config.PATHS.OUTPUT_DIR),
                "log_file": str(log_file),
                "steps": selected_steps,
                "sample_count": len(replicate_groups),
                "duration_seconds": round(total_time, 3),
            }

            _emit_progress(
                progress_callback,
                step="pipeline",
                status="success",
                message="Étapes sélectionnées terminées",
                progress=1.0,
            )

            return pipeline_result

        if selected_steps == ["blanks"]:
            _emit_progress(
                progress_callback,
                step="blanks",
                status="running",
                message="Traitement des blanks",
                progress=0.30,
            )

            discovered = discover_input_files(
                require_samples=False
            )
            blank_files = discovered["blank_files"]
            blank_peaks = pd.DataFrame()
            blank_peaks_file = None

            print("\n" + "=" * 80)
            print("TRAITEMENT AUTONOME DES BLANKS")
            print("=" * 80)

            if blank_files:
                print(
                    f"   • {len(blank_files)} fichier(s) blank trouvé(s)"
                )

                blank_peaks = (
                    blank_processor.process_blank_with_replicates(
                        blank_files[0].stem,
                        blank_files,
                        Config.PATHS.INTERMEDIATE_DIR / "blanks",
                    )
                )

                blank_peaks_file = save_blank_peaks(blank_peaks)

                print(
                    "   ✓ Résultat sauvegardé : "
                    f"{blank_peaks_file}"
                )
            else:
                print(
                    "   ℹ Aucun fichier blank trouvé. "
                    "Aucune soustraction ne sera nécessaire."
                )

            total_time = time.time() - start_time

            pipeline_result = {
                "status": "success",
                "base_dir": str(Config.PATHS.BASE_DIR),
                "output_dir": str(Config.PATHS.OUTPUT_DIR),
                "log_file": str(log_file),
                "steps": selected_steps,
                "sample_count": 0,
                "blank_file_count": len(blank_files),
                "blank_count": len(blank_peaks),
                "blank_peaks_file": (
                    str(blank_peaks_file)
                    if blank_peaks_file is not None
                    else None
                ),
                "duration_seconds": round(total_time, 3),
            }

            _emit_progress(
                progress_callback,
                step="pipeline",
                status="success",
                message="Étapes sélectionnées terminées",
                progress=1.0,
            )

            return pipeline_result

        if selected_steps == ["samples"]:
            _emit_progress(
                progress_callback,
                step="samples",
                status="running",
                message="Traitement autonome des échantillons",
                progress=0.40,
            )

            print("\n" + "=" * 80)
            print("TRAITEMENT AUTONOME DES ÉCHANTILLONS")
            print("=" * 80)

            calibration_file = (
                Config.PATHS.INPUT_CALIBRANTS
                / "CCS_calibration_data.csv"
            )

            if not calibration_file.exists():
                raise FileNotFoundError(
                    "Fichier de calibration non trouvé : "
                    f"{calibration_file}"
                )

            calibrator = CCSCalibrator(calibration_file)

            discovered = discover_input_files(
                require_samples=True
            )

            blank_files = discovered["blank_files"]
            replicate_groups = discovered["replicate_groups"]

            blank_peaks = load_optional_blank_peaks(
                blank_files
            )

            if blank_peaks.empty:
                print(
                    "   ℹ Aucun résultat de blank appliqué"
                )
            else:
                print(
                    "   ✓ Résultat des blanks rechargé : "
                    f"{len(blank_peaks)} pics"
                )

            sample_results = process_samples_parallel(
                replicate_groups,
                blank_peaks,
                calibrator,
                Config.PATHS.INTERMEDIATE_SAMPLES,
            )

            successful_samples = {
                name: result
                for name, result in sample_results.items()
                if result.success
            }

            if not successful_samples:
                raise RuntimeError(
                    "Aucun échantillon n'a été traité avec succès"
                )

            total_time = time.time() - start_time

            pipeline_result = {
                "status": "success",
                "base_dir": str(Config.PATHS.BASE_DIR),
                "output_dir": str(Config.PATHS.OUTPUT_DIR),
                "intermediate_samples_dir": str(
                    Config.PATHS.INTERMEDIATE_SAMPLES
                ),
                "log_file": str(log_file),
                "steps": selected_steps,
                "sample_count": len(replicate_groups),
                "successful_sample_count": len(
                    successful_samples
                ),
                "blank_count": len(blank_peaks),
                "duration_seconds": round(total_time, 3),
            }

            _emit_progress(
                progress_callback,
                step="pipeline",
                status="success",
                message="Étapes sélectionnées terminées",
                progress=1.0,
            )

            return pipeline_result

        if selected_steps == ["feature_alignment"]:
            _emit_progress(
                progress_callback,
                step="feature_alignment",
                status="running",
                message="Alignement des features et identification",
                progress=0.70,
            )

            print("\n" + "=" * 80)
            print("ALIGNEMENT AUTONOME DES FEATURES")
            print("=" * 80)

            common_peaks_files = sorted(
                Config.PATHS.INTERMEDIATE_SAMPLES.glob(
                    "*/ms1/common_peaks.parquet"
                )
            )

            if not common_peaks_files:
                raise FileNotFoundError(
                    "Aucun résultat intermédiaire d'échantillon trouvé "
                    "dans "
                    f"{Config.PATHS.INTERMEDIATE_SAMPLES}. "
                    "Exécutez d'abord l'étape 'samples'."
                )

            database_file = (
                Config.PATHS.INPUT_DATABASES
                / Config.IDENTIFICATION.database_file
            )

            if not database_file.exists():
                raise FileNotFoundError(
                    "Base de données d'identification non trouvée : "
                    f"{database_file}"
                )

            print(
                "   • Résultats intermédiaires détectés : "
                f"{len(common_peaks_files)}"
            )
            print(
                "   • Base d'identification : "
                f"{database_file.name}"
            )

            identifier = CompoundIdentifier()
            feature_output_dir = (
                Config.PATHS.OUTPUT_DIR
                / "feature_matrix"
            )

            feature_processor.create_feature_matrix(
                input_dir=Config.PATHS.INTERMEDIATE_SAMPLES,
                output_dir=feature_output_dir,
                identifier=identifier,
            )

            feature_matrix_file = (
                feature_output_dir
                / "feature_matrix.parquet"
            )
            features_complete_file = (
                feature_output_dir
                / "features_complete.parquet"
            )

            if not feature_matrix_file.exists():
                raise RuntimeError(
                    "La matrice de features n'a pas été produite : "
                    f"{feature_matrix_file}"
                )

            total_time = time.time() - start_time

            pipeline_result = {
                "status": "success",
                "base_dir": str(Config.PATHS.BASE_DIR),
                "output_dir": str(Config.PATHS.OUTPUT_DIR),
                "feature_output_dir": str(
                    feature_output_dir
                ),
                "feature_matrix_file": str(
                    feature_matrix_file
                ),
                "features_complete_file": (
                    str(features_complete_file)
                    if features_complete_file.exists()
                    else None
                ),
                "log_file": str(log_file),
                "steps": selected_steps,
                "sample_count": len(common_peaks_files),
                "duration_seconds": round(total_time, 3),
            }

            _emit_progress(
                progress_callback,
                step="pipeline",
                status="success",
                message="Étapes sélectionnées terminées",
                progress=1.0,
            )

            return pipeline_result

        # 1. Chargement des données de calibration CCS
        _emit_progress(
            progress_callback,
            step="calibration",
            status="running",
            message="Chargement de la calibration CCS",
            progress=0.05,
        )
        print("\n📈 Chargement des données de calibration CCS...")
        calibration_file = Config.PATHS.INPUT_CALIBRANTS / "CCS_calibration_data.csv"
        if not calibration_file.exists():
            raise FileNotFoundError(f"Fichier de calibration non trouvé : {calibration_file}")
        calibrator = CCSCalibrator(calibration_file)
        print("   ✓ Données de calibration chargées avec succès")

        # 2. Initialisation de l'identificateur
        _emit_progress(
            progress_callback,
            step="identification",
            status="running",
            message="Chargement de la base d'identification",
            progress=0.12,
        )
        print("\n📚 Initialisation de l'identification...")
        identifier = CompoundIdentifier()
        print("   ✓ Base de données chargée avec succès")
        
        # Recherche des fichiers
        _emit_progress(
            progress_callback,
            step="file_discovery",
            status="running",
            message="Détection des fichiers d'entrée",
            progress=0.20,
        )
        print("\n📁 Recherche des blanks...")
        blank_dir = Config.PATHS.INPUT_BLANKS
        blank_files = list(blank_dir.glob("*.parquet"))

        # Affichage des informations sur les blanks
        if blank_files:
            print(f"   ✓ {len(blank_files)} fichier(s) blank trouvé(s):")
            for blank_file in blank_files:
                print(f"      - {blank_file.name}")
        else:
            print("   ℹ️ Aucun fichier blank trouvé dans data/input/blanks/")

        print("\n📁 Recherche des échantillons...")
        samples_dir = Config.PATHS.INPUT_SAMPLES
        sample_files = list(samples_dir.glob("*.parquet"))

        if not sample_files:
            raise ValueError("Aucun fichier d'échantillon trouvé.")
            
        replicate_handler = ReplicateHandler()
        replicate_groups = replicate_handler.group_replicates(sample_files)
        print(f"   ✓ {len(replicate_groups)} échantillons trouvés:")
        for base_name, replicates in replicate_groups.items():
            print(f"      - {base_name}: {len(replicates)} réplicat(s)")

        # 5. Traitement des blanks
        _emit_progress(
            progress_callback,
            step="blanks",
            status="running",
            message="Traitement des blanks",
            progress=0.30,
        )
        print("\n" + "="*80)
        print("TRAITEMENT DES BLANKS")
        print("=" * 80)
        
        blank_peaks = pd.DataFrame()
        if blank_files:
            blank_peaks = blank_processor.process_blank_with_replicates(
                blank_files[0].stem,
                blank_files,
                Config.PATHS.INTERMEDIATE_DIR / "blanks"
            )

            blank_peaks_file = save_blank_peaks(blank_peaks)
            print(
                "   ✓ Résultat des blanks sauvegardé : "
                f"{blank_peaks_file}"
            )
        else:
            print(
                "   ℹ Aucun blank brut : aucune soustraction "
                "ne sera appliquée"
            )

# 6. Traitement des échantillons
        _emit_progress(
            progress_callback,
            step="samples",
            status="running",
            message="Traitement des échantillons",
            progress=0.40,
        )
        print("\n" + "="*80)
        print("TRAITEMENT DES ÉCHANTILLONS")
        print("=" * 80)

        results = process_samples_parallel(
            replicate_groups,
            blank_peaks,
            calibrator,
            Config.PATHS.INTERMEDIATE_SAMPLES
        )
        
        # Vérifier si des échantillons ont été traités avec succès
        if not any(r.success for r in results.values()):
            raise Exception("Aucun échantillon n'a été traité avec succès")

        _emit_progress(
            progress_callback,
            step="feature_alignment",
            status="running",
            message="Alignement des features et identification",
            progress=0.70,
        )

        print("\n" + "="*80)
        print("ALIGNEMENT DES FEATURES")
        print("="*80)
        
        # 7. Feature Matrix et identification
        print("\n📊 Création de la matrice des features...")
        feature_processor.create_feature_matrix(
            input_dir=Config.PATHS.INTERMEDIATE_SAMPLES,
            output_dir=Config.PATHS.OUTPUT_DIR / "feature_matrix",
            identifier=identifier
        )

        _emit_progress(
            progress_callback,
            step="visualizations",
            status="running",
            message="Génération des visualisations",
            progress=0.82,
        )

        print("\n" + "="*80)
        print("GÉNÉRATION DES VISUALISATIONS")
        print("="*80)
        
        # 8. Visualisations
        output_dir = Config.PATHS.OUTPUT_DIR
        generate_visualizations(output_dir)
        
        _emit_progress(
            progress_callback,
            step="similarities",
            status="running",
            message="Analyse des similarités",
            progress=0.90,
        )

        print("\n" + "="*80)
        print("ANALYSE DES SIMILARITÉS")
        print("="*80)
        
        print("\n📊 Analyse des clusters d'échantillons...")
        analyze_and_save_clusters(output_dir)

        _emit_progress(
            progress_callback,
            step="categories",
            status="running",
            message="Analyse des catégories",
            progress=0.95,
        )

        print("\n" + "="*80)
        print("ANALYSE DES CATÉGORIES")
        print("="*80)
    
        print("\n📊 Analyse des catégories de molécules...")
        analyze_categories(output_dir)

        # Affichage du récapitulatif
        total_time = time.time() - start_time
        minutes = int(total_time // 60)
        seconds = int(total_time % 60)
        
        print("\n" + "="*80)
        print(" ✅ FIN DU TRAITEMENT")
        print("="*80)
        print("\n Pipeline d'analyse terminée avec succès")
        if minutes > 0:
            print(f"   • Temps de calcul total: {minutes} min {seconds} sec")
        else:
            print(f"   • Temps de calcul total: {seconds} sec")
        print(f"   • {len(replicate_groups)} échantillons traités")
        print("=" * 80)

        pipeline_result = {
            "status": "success",
            "base_dir": str(Config.PATHS.BASE_DIR),
            "output_dir": str(Config.PATHS.OUTPUT_DIR),
            "log_file": str(log_file),
            "steps": selected_steps,
            "sample_count": len(replicate_groups),
            "duration_seconds": round(total_time, 3),
        }

        _emit_progress(
            progress_callback,
            step="pipeline",
            status="success",
            message="Pipeline terminée",
            progress=1.0,
        )

        return pipeline_result

    except Exception as e:
        print("\n❌ ERREUR DANS LA PIPELINE")
        logger.error(f"Erreur pipeline : {str(e)}")
        _emit_progress(
            progress_callback,
            step="pipeline",
            status="error",
            message=str(e),
            progress=None,
        )
        raise

def main() -> None:
    """Point d'entrée historique pour le lancement en ligne de commande."""
    run_pipeline()


if __name__ == "__main__":
    main()