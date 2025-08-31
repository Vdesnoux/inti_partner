
"""
Inti_partner
Author : Valerie Desnoux

2025

"""

import sys
import os, fnmatch
import yaml as yaml
import pyqtgraph as pg
from pyqtgraph.exporters import ImageExporter
from pyqtgraph import ImageView, PlotWidget, LinearRegionItem
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import QApplication,QMenu,QGraphicsPathItem, QGraphicsPixmapItem,QMainWindow,QDialog, QDockWidget, QFileDialog,QMessageBox, QTableWidgetItem, QWidget,QGraphicsLineItem, QListWidgetItem, QVBoxLayout,QGraphicsEllipseItem
from PySide6.QtCore import QFile, QIODevice, Qt, QSettings, QTimer,QTranslator, QUrl, QRect, Signal, QPoint
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6 import QtGui
from astropy.io import fits
import astropy.time
import numpy as np
from PIL import Image
import dedistord as ddist
import cv2 as cv2
import mosaic as mo
from scipy.interpolate import interp1d
#from scipy.ndimage import gaussian_filter1d
import magnet as magnet
import datetime
import math
import requests as rq
import webbrowser as web
from pathlib import Path
from serfilesreader_vhd import Serfile # Version custom pour ecriture fichier SER

from skimage.segmentation import disk_level_set
from skimage.util import invert

import requests
import subprocess

# Rediriger matplotlib vers mon cache local
local_cache = os.path.join(os.path.dirname(__file__), 'matplotlib_cache')
os.environ['MPLCONFIGDIR'] = local_cache
import matplotlib.pyplot as plt #only for debug

import time #only for debug

"""
Version 0.4 - 13 avril 2025
- première version publique

Version 0.5 - 31 mai 2025
- ajout tab viewer, gestion image couleur, fits et sauvegarde si modif seuils
- transfer dans l'onglet qui va bien ser ou proc
- ajout dans proc d'un angle de rotation et d'angle P
- ajout visu log.txt ou header dans proc tab
- lecture tiff
- lance  inti depuis viewer 
- save fits depuis un png
- ajout de traitements clahe, aussi en couleur
- gestion des repertoires d'onglet à onglet
- ajout gestion log.txt dans mosa pour les clahe
- ajout read ini avec seuil pour stack
- ajout somme stack simple en fits
- couleur Helium et Sodium plus forte
- met les fichiers st dans un repetoire stack
- ajout annotations distance et terre

Version 0.7 - 17 juillet 2025
- ajout label Terre
- gestion repertoire clahe pour trouver cont en stack et animation
- affichage gong comme inti
- sous-repertoire anim
- fond presque noir pour image grille
- annotations dans le prolongement des arc de cercles
- ajout de selection _free dans stack, proc, grille etc

Version 0.8 - Aout 2025
- remplace ouverture fichiers par ouverture repertoire, plus logique
- affiche images disk png au lancment si tab viewer est le current tab
- but fix sur autorange des images dans selector au lancement avec un wait
- bug fix nom inti.exe
- ajout changer repertoire INTI
- ajout infinite line sur ser pour defile profile avec trame et souris
- ajout d'un saveas trame dans onglet ser
- ajout correction bandes vert dans magnet
- annotations disque partiel

"""
# TODO : resize sur les diam de disque pour animation
# TODO : saveas annotation image carré, zoom, juste un coin

# IDEAS: lire infos comme date et heure image, ser
# IDEAS: lecture ser en memmap 
# IDEAS: effacer un fichier, effacer tous ser et famille de la racine
# IDEAS: popup demande de la date, ou du rayon si ne trouve pas le fichier log 
# IDEAS: prendre rotation en compte dans magnet
# IDEAS: ajout carte synoptique
# IDEAS: save png avec seuils



class main_wnd_UI(QMainWindow) :
    def __init__(self, parent=None):
       
        #super().__init__(parent)
        super(main_wnd_UI, self).__init__()
        
        self.version ="0.8"
        
        #fichier GUI par Qt Designer
        loader = QUiLoader()
        loader.registerCustomWidget(ImageView)
        loader.registerCustomWidget(PlotWidget)
        ui_file_name=resource_path('inti_partner.ui')
        ui_file = QFile(ui_file_name)
        
        if not ui_file.open(QIODevice.ReadOnly):
            print(f"Cannot open {ui_file_name}: {ui_file.errorString()}")
            sys.exit(-1)
        
        self.ui = loader.load(ui_file)
        ui_file.close()
        

        self.read_settings()
        self.read_ini()
       
        
        # set icon application
        self.ui.setWindowIcon(QtGui.QIcon(resource_path("intipartner_icon.png")))
        
        # connect window close button to closeEvent
        app.aboutToQuit.connect(self.close)
        
        # redirect les print vers le textEdit console
        sys.stdout = Log(self.ui.log_edit)
        
       
        # gestion langue

        if self.langue=='En' :
           self.ui.lang_button.setText('En')
        else :
           self.ui.lang_button.setText('Fr')

        
        # init param
        self.myROI=[]
        self.pattern=''
        
        # force mode compact
        self.ui.main_dock.setMinimumSize(0, 0)
        self.ui.tab_main.setMinimumSize(0, 0)
        
        self.circle_list=[]
        self.label_list=[]
        self.line_list=[]
        self.terre_list=[]
    
        
        # connecte les signaux
        # lang & exit & version
        self.ui.Exit.clicked.connect(self.exit_clicked)
        self.ui.lang_button.clicked.connect(self.lang_switch_clicked)
        self.ui.version_label.setText("Version : "+self.version)
        self.ui.tab_main.currentChanged.connect(self.on_tab_changed)
        
        # tab viewer
        # ------------------------------------------------------------------
        # signaux
        #self.ui.view_open_btn.clicked.connect(self.view_open_clicked)
        self.ui.view_dir_open_btn.clicked.connect(self.view_dir_open_clicked)
        self.ui.view_clahe_btn.clicked.connect(lambda: self.view_filtre_clicked("clahe"))
        self.ui.view_protus_btn.clicked.connect(lambda: self.view_filtre_clicked("protus"))
        self.ui.view_color_btn.clicked.connect(lambda: self.view_filtre_clicked("color"))
        self.ui.view_cont_btn.clicked.connect(lambda: self.view_filtre_clicked("cont"))
        self.ui.view_doppler_btn.clicked.connect(lambda: self.view_filtre_clicked("doppler"))
        self.ui.view_free_btn.clicked.connect(lambda: self.view_filtre_clicked("free"))
        self.ui.view_raw_btn.clicked.connect(lambda: self.view_filtre_clicked("raw"))
        self.ui.view_disk_btn.clicked.connect(lambda: self.view_filtre_clicked("disk"))
        self.ui.view_tous_btn.clicked.connect(lambda: self.view_filtre_clicked("tous"))
        #self.ui.view_add_btn.clicked.connect(self.view_add_open_clicked)
        self.ui.buttonGroup_2.idClicked.connect(self.view_radio_clicked)
        self.ui.img_list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.img_list_view.customContextMenuRequested.connect(self.view_open_context_menu)

        
        
        # tab stack
        # ------------------------------------------------------------------
        # signaux
        self.ui.stack_img_list_open.clicked.connect(self.stack_img_list_open_clicked)
        self.ui.run_app_btn.clicked.connect(self.run_stack_clicked)
        self.ui.stack_img_list_view.selectionModel().selectionChanged.connect(self.stack_img_list_view_sel_changed)
        self.ui.stack_list.itemClicked.connect(self.stack_list_clicked)
        self.ui.stack_list_result.itemClicked.connect(self.stack_list_result_clicked)
        self.ui.stack_image_view.scene.sigMouseMoved.connect(self.on_mouse_move)
        self.ui.stack_remove_btn.clicked.connect(self.stack_remove_item)
        self.ui.stack_open_sel_list_btn.clicked.connect(self.stack_open_sel_list)
        self.ui.stack_save_list_btn.clicked.connect(self.stack_save_list)
        self.ui.stack_flip_hb_btn.clicked.connect(self.stack_flip_hb)
        self.ui.stack_flip_dg_btn.clicked.connect(self.stack_flip_dg)
        self.ui.stack_progress_bar.setVisible(False)

        # setting
        self.ui.stack_image_view.ui.roiBtn.hide()
        self.ui.stack_image_view.ui.menuBtn.hide()
        self.ui.stack_image_view.ui.histogram.hide()
        
        
        # tab selector
        # ------------------------------------------------------------------
        # signaux
        self.ui.select_open_dir_btn.clicked.connect(self.select_open_dir_clicked)
        self.ui.select_pattern_combo.currentIndexChanged.connect(self.select_pattern_clicked)
        self.ui.select_ref_btn.clicked.connect(self.select_ref_clicked)
        self.ui.select_log_btn.clicked.connect(self.select_log_clicked)
        self.ui.select_next_btn.clicked.connect(self.select_next_clicked)
        self.ui.select_prev_btn.clicked.connect(self.select_prev_dir_clicked)
        self.ui.select_remove_btn.clicked.connect(self.select_remove_clicked)
        self.ui.select_list_files.itemClicked.connect(self.select_file_item_clicked)
        self.ui.select_files_sel_list.itemClicked.connect(self.select_selfile_item_clicked)
        self.ui.select_order_files_byiqm_btn.clicked.connect(self.sort_files_IQ)
        self.ui.select_order_files_byname_btn.clicked.connect(self.sort_files_name)
        self.ui.select_open_sel_list_btn.clicked.connect(self.select_open_list)
        self.ui.select_saveas_sel_list_btn.clicked.connect(self.select_save_list)
        self.ui.select_clear_sel_btn.clicked.connect(self.select_clear_sel)
        self.ui.select_new_base_list.clicked.connect(self.select_new_base)
        self.ui.select_flip_hb_btn.clicked.connect(self.select_flip_hb)
        self.ui.select_flip_dg_btn.clicked.connect(self.select_flip_dg)
        
        # setting
        self.ui.select_image_view_ref.ui.roiBtn.hide()
        self.ui.select_image_view_ref.ui.menuBtn.hide()
        self.ui.select_image_view_ref.ui.histogram.hide()
        
        self.ui.select_image_view.ui.roiBtn.hide()
        self.ui.select_image_view.ui.menuBtn.hide()
        self.ui.select_image_view.ui.histogram.hide()
        
        pattern_list=['*_disk.png', '*_clahe.png', '*_protus.png', '*_cont.png', '*_free.png', '*.png']
        self.ui.select_pattern_combo.addItems(pattern_list)
        self.ui.select_pattern_combo.setCurrentIndex(0)
        
        #page = self.ui.tab_main.findChild(QWidget, 'tab_selector')
        #self.ui.tab_main.setCurrentWidget(page)
        
        # tab mosa
        # ------------------------------------------------------------------
        # signaux
        self.ui.mosa_img_open.clicked.connect(self.mosa_img_open_clicked)
        self.ui.run_mosa_btn.clicked.connect(self.run_mosa_clicked)
        self.ui.mosa_img_list_view.selectionModel().selectionChanged.connect(self.mosa_img_list_view_sel_changed)
        self.ui.mosa_image_view.scene.sigMouseMoved.connect(self.on_mouse_move)
        
        
        # setting
        self.ui.mosa_image_view.ui.roiBtn.hide()
        self.ui.mosa_image_view.ui.menuBtn.hide()
        self.ui.mosa_image_view.ui.histogram.hide()       
        
        # tab anim
        # ------------------------------------------------------------------
        self.ui.anim_img_list_open_btn.clicked.connect(self.anim_img_list_open_clicked)
        self.ui.anim_list.selectionModel().selectionChanged.connect(self.anim_list_sel_changed)
        self.ui.anim_next_btn.clicked.connect(self.anim_next_clicked)
        self.ui.anim_prev_btn.clicked.connect(self.anim_prev_clicked)
        self.ui.anim_remove_btn.clicked.connect(self.anim_remove_clicked)
        self.ui.anim_image_view.scene.sigMouseMoved.connect(self.on_mouse_move)
        self.ui.anim_flip_hb_btn.clicked.connect(self.anim_flip_hb)
        self.ui.anim_flip_dg_btn.clicked.connect(self.anim_flip_dg)
        self.ui.anim_roi_btn.clicked.connect(self.anim_roi)
        self.ui.anim_crop_btn.clicked.connect(self.anim_crop)
        self.ui.anim_reset_btn.clicked.connect(self.anim_reset)
        self.ui.anim_add_img_btn.clicked.connect(self.anim_add_img)
        self.ui.anim_create_btn.clicked.connect(self.anim_create)
        self.ui.anim_stacked_widget.setCurrentIndex(0)
        self.ui.anim_play_btn.clicked.connect(self.anim_play)
        self.ui.anim_nb_total_text.editingFinished.connect(self.anim_time_sample_validate)
        self.ui.anim_fps_text.editingFinished.connect(self.anim_time_sample_validate)
        self.ui.anim_progress_bar.setVisible(False)
        self.ui.anim_image_view.view.setBackgroundColor((20,20,20))
        self.ui.anim_interp_checkbox.stateChanged.connect(self.anim_interp)
        self.ui.anim_open_sel_list_btn.clicked.connect(self.anim_open_sel_list)
        self.flag_nologtxt=False
        
        self.myfilter=''
        
        # setting
        self.ui.anim_image_view.ui.roiBtn.hide()
        self.ui.anim_image_view.ui.menuBtn.hide()
        self.ui.anim_image_view.ui.histogram.hide()   
        
        # add video player to stacked widget
        self.anim_video_player = QVideoWidget(self.ui.anim_video_frame)
        self.anim_video_player.setObjectName("anim_video_player")
        #self.anim_video_player.setGeometry(QRect(10, 10, 400, 400))
        layout =  QVBoxLayout()
        layout.addWidget(self.anim_video_player)
        layout.addWidget(self.ui.anim_play_btn)
        self.ui.anim_video_frame.setLayout(layout)
        
        # tab map
        # -----------------------------------------------------------------
        
        # setting
        self.ui.map_image_ref_view.ui.roiBtn.hide()
        self.ui.map_image_ref_view.ui.menuBtn.hide()
        self.ui.map_image_ref_view.ui.histogram.hide()   
        
        self.ui.map_image_color_view.ui.roiBtn.hide()
        self.ui.map_image_color_view.ui.menuBtn.hide()
        self.ui.map_image_color_view.ui.histogram.hide()  
        
        self.ui.map_reset_btn.clicked.connect(self.map_reset)
        self.ui.map_goto_combo.currentTextChanged.connect(self.map_goto)
        self.ui.map_open_btn.clicked.connect(self.map_image_open)
        self.ui.map_localise_btn.clicked.connect(self.map_localize)
        
        # image color
        img_color=resource_path('sun_spectre_color.png')
        image_data = cv2.imread(img_color)
        image_data=cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
        ih,iw,nbplan= np.array(image_data).shape
        self.map_color_ih=ih
        self.map_color_iw=iw
        rotated_data = np.fliplr(np.rot90(image_data, 3))
        self.ui.map_image_color_view.view.setAspectLocked(False)
        self.ui.map_image_color_view.view.setRange(xRange=[0,iw], yRange=[0,ih], padding=0)
        self.ui.map_image_color_view.view.setMouseEnabled(False,False)
        self.ui.map_image_color_view.view.setMenuEnabled(False)
        self.ui.map_image_color_view.setImage(rotated_data,autoRange=False, autoLevels=True)
        
        # image annot
        img_ref=resource_path('sun_spectre_annot_V2.png')
        image_data = cv2.imread(img_ref)
        image_data=cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
        ih,iw,nbplan= np.array(image_data).shape
        self.map_iw=iw
        self.map_ih=ih
        rotated_data = np.fliplr(np.rot90(image_data, 3))
        self.ui.map_image_ref_view.view.setAspectLocked(False)
        self.ui.map_image_ref_view.view.setMouseEnabled(False,True)
        self.ui.map_image_ref_view.view.setRange(xRange=[200,iw], yRange=[0,1500], padding=0)
        self.ui.map_image_ref_view.setImage(rotated_data,autoRange=False, autoLevels=True)
        
        # tab magnet
        #-------------------------------------------------------------------
        
        # setting
        self.ui.mag_img_view.ui.roiBtn.hide()
        self.ui.mag_img_view.ui.menuBtn.hide()
        
        self.ui.mag_droite_open_btn.clicked.connect(self.mag_droite_open)
        self.ui.mag_gauche_open_btn.clicked.connect(self.mag_gauche_open)
        self.ui.mag_go_btn.clicked.connect(self.mag_go)
        self.ui.mag_img_view.scene.sigMouseMoved.connect(self.on_mouse_move)
        self.ui.mag_droite_list.selectionModel().selectionChanged.connect(self.mag_droite_list_sel_changed)
        self.ui.mag_gauche_list.selectionModel().selectionChanged.connect(self.mag_gauche_list_sel_changed)
        self.ui.mag_results_list.selectionModel().selectionChanged.connect(self.mag_results_list_sel_changed)
        
        # tab SER
        #-------------------------------------------------------------------
        
        # setting
        self.ui.ser_view.ui.roiBtn.hide()
        self.ui.ser_view.ui.menuBtn.hide()
        #self.ui.ser_view.ui.histogram.hide()
        self.ui.ser_view.view.setBackgroundColor((20,20,20))
        
        self.ui.ser_raw_view.ui.roiBtn.hide()
        self.ui.ser_raw_view.ui.menuBtn.hide()
        #self.ui.ser_raw_view.ui.histogram.hide()
        
        self.ui.ser_open_btn.clicked.connect(self.ser_open)
        self.ui.ser_view.sigTimeChanged.connect(self.ser_frame_changed)
        self.ui.ser_play_btn.clicked.connect(self.ser_play)
        self.ui.ser_stop_btn.clicked.connect(self.ser_stop)
        self.ui.ser_saveas_btn.clicked.connect(self.ser_saveas)
        self.ui.ser_view.scene.sigMouseClicked.connect(self.on_mouse_click)
        self.ui.ser_view.scene.sigMouseMoved.connect(self.on_mouse_move)
        self.ui.ser_posx_prev_btn.clicked.connect(self.ser_posx_prev)
        self.ui.ser_posx_next_btn.clicked.connect(self.ser_posx_next)
        self.ui.ser_goto_frame_text.editingFinished.connect(self.ser_goto_frame)
        self.ser_posx=0
        self.ui.ser_trim_save_btn.clicked.connect(self.ser_trim_save)
        
        self.v_bar = pg.InfiniteLine(movable=True, angle=90,pen=pg.mkPen(QtGui.QColor(250,250,0,0x60),width=4), label='{value}', 
                        labelOpts={'position': 0.1, 'anchors':[(0.5, 0), (0.5, 1)],'color': 'black', 'fill': "white",'movable': True}) #"border": "grey"
        self.v_bar.sigDragged.connect(self.ser_raw_cursor_sig_dragged)
        
        self.v_bar_pro = pg.InfiniteLine(movable=True, angle=90,pen=pg.mkPen(QtGui.QColor(0,250,250,0x60),width=4)) #"border": "grey"
        self.v_bar_pro.sigDragged.connect(self.ser_trame_cursor_sig_dragged)

        
        # config plot profile spectral
        self.ui.spectre_view.setBackground('w')
        pen_axis=pg.mkPen(color="black",width=2)
        pen_axis2=pg.mkPen(color="w",width=1)
        self.ui.spectre_view.getAxis('left').setPen(pen_axis)
        self.ui.spectre_view.getAxis('bottom').setPen(pen_axis)
        self.ui.spectre_view.getAxis("left").setTextPen(pen_axis)
        self.ui.spectre_view.getAxis("bottom").setTextPen(pen_axis)

        self.ui.spectre_view.showAxis("right")
        self.ui.spectre_view.showAxis("top")
        self.ui.spectre_view.getAxis('top').setPen(pen_axis)
        self.ui.spectre_view.getAxis('right').setPen(pen_axis)
        self.ui.spectre_view.getAxis("top").setTextPen(pen_axis2)
        self.ui.spectre_view.getAxis("right").setTextPen(pen_axis2)
       

        # tab proc
        # -------------------------------------------------------------------
        
        # settings
        self.ui.proc_view.ui.roiBtn.hide()
        self.ui.proc_view.ui.menuBtn.hide()
        self.ui.proc_view.view.setBackgroundColor((20,20,20))
        
        self.ui.proc_open_btn.clicked.connect(self.proc_open)
        self.ui.proc_apply_btn.clicked.connect(self.proc_apply)
        self.ui.proc_undo_btn.clicked.connect(self.proc_undo)
        self.ui.proc_saveas_btn.clicked.connect(self.proc_saveas)
        self.ui.proc_crop_test_btn.clicked.connect(self.proc_crop_test)
        self.ui.proc_crop_btn.clicked.connect(self.proc_crop)
        self.ui.proc_view.scene.sigMouseMoved.connect(self.on_mouse_move)
        #self.ui.proc_color_combo.currentTextChanged.connect(self.proc_color)
        self.ui.proc_helium_btn.clicked.connect(self.proc_helium)
        self.ui.proc_magnet_btn.clicked.connect(self.proc_magnet)
        self.ui.proc_angP_btn.clicked.connect(self.proc_angP)
        #self.ui.proc_ang_btn.clicked.connect(self.proc_ang)
        self.ui.proc_infos_btn.clicked.connect(self.proc_infos)
        
        
        # tab grid
        # -------------------------------------------------------------------
        
        # settings
        self.ui.grid_view.ui.roiBtn.hide()
        self.ui.grid_view.ui.menuBtn.hide()
        self.ui.grid_view.view.setBackgroundColor((5,5,5)) # was 20,20,20 - permet fond noir pour annotations
        #font = QtGui.QFont('Arial', 6)
        #self.ui.grid_view.setFont(font)
        
        self.ui.grid_open_btn.clicked.connect(self.grid_open)
        self.ui.grid_on_btn.clicked.connect(self.grid_plot)
        self.ui.grid_hb_btn.clicked.connect(self.grid_hb)
        self.ui.grid_dg_btn.clicked.connect(self.grid_dg)
        self.ui.grid_gong_btn.clicked.connect(self.grid_gong)
        self.ui.grid_saveas_btn.clicked.connect(self.grid_saveas)
        #self.ui.grid_applyP_btn.clicked.connect(self.grid_rotate)
        self.ui.grid_annuler_btn.clicked.connect(self.grid_annuler)
        self.ui.grid_fili_cancel_btn.clicked.connect(self.grid_fili_cancel)
        self.ui.grid_fili_display_btn.clicked.connect(self.grid_fili_display)
        self.plotitem=[]
        self.ui.grid_dist_btn.clicked.connect(self.grid_dist)
        self.ui.grid_dist_cancel_btn.clicked.connect(self.grid_dist_cancel)
        self.ui.grid_terre_btn.clicked.connect(self.grid_terre)
        self.ui.grid_terre_cancel_btn.clicked.connect(self.grid_terre_cancel)
        self.img_earth=resource_path('earth.png')

        #--------------------------------------------------------------------
        # init param application
        #--------------------------------------------------------------------
        # inticompagnon.yaml is a bootstart file to read last directory used by app
        # this file is stored in the module directory
        
        self.my_ini=data_path('intipartner_ini.yaml')
        self.my_dictini={'working_dir':'',
                    'lang' : 'Fr'
                    }
    
        try:
            with open(self.my_ini, "r") as f1:
                self.my_dictini = yaml.safe_load(f1)        
        except:
            print(self.tr('Création du fichier intipartner_ini.yaml: '), self.my_ini)
               
        try :
            self.langue=self.my_dictini['lang']
        except:
            self.langue='Fr'
            
        try :
            self.working_dir=self.my_dictini['working_dir']
        except:
            self.working_dir=''
    
        # on teste version du web
        self.check_version()
        
        # selectionne tab du tab widget et le widget panel depuis settings app
        try :
            self.ui.tab_main.setCurrentIndex(self.current_tab)
            self.ui.panelWidget.setCurrentIndex(self.current_tab)
        except:
            self.ui.tab_main.setCurrentIndex(0)
            self.ui.panelWidget.setCurrentIndex(0)
        #self.ui.view_dir_lbl.setText(self.working_dir) 
        self.ui.view_dir2_lbl.setText(self.working_dir)
        self.ui.select_dir_lbl.setText(self.working_dir) 
        
        # force antialiasing option de pyqtgraph
        pg.setConfigOptions(antialias=True)
    
    
    def show(self) :
        self.ui.show()
        self.ui.dock_console.show()
        self.on_tab_changed(self.current_tab)
       
    
    def closeEvent (self,event):
        try :
            self.save_ini()
            self.write_settings()
        except :
            pass

        
    def exit_clicked(self) :
        self.save_ini()
        self.write_settings()
        for dock in self.ui.findChildren(QDockWidget):
            
            if dock.isFloating() :
                #print(dock.windowTitle())
                dock.close()
                self.ui.dock_console.hide()
        QApplication.instance().quit()
        app.quit()

 
    def lang_switch_clicked (self):
        if self.ui.lang_button.text()=='Fr' :
            self.ui.lang_button.setText('En')
            self.langue='En'
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("Restart application to change language")
            msg.setWindowTitle("Message")
            msg.exec()
        else:
            self.ui.lang_button.setText('Fr')
            self.langue='Fr'
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setText("Redémarrer l'application pour changer la langue")
            msg.setWindowTitle("Message")
            msg.exec()
            
    def on_tab_changed(self, index) :
        self.current_tab = index

        # tab viewer
        if index == 0 or index ==1 :
            # si deja images alors ne pas relire le repertoire
            if self.working_dir !='' and self.ui.img_list_view.count() == 0:
                self.ui.select_list_files.clear()
                self.ui.select_files_sel_list.clear()
                self.iqm_list=[]
                self.selected_files=[]
                self.select_read()
                self.view_radio_clicked()


    def read_ini(self) :
        # recuperation des parametres de configuration memorisé au dernier traitement
        # --------------------------------------------------------------------------------------

        self.my_ini=data_path('intipartner_ini.yaml')
        my_dictini={'working_dir':'', 'lang' :'Fr', 'stack_seuil':1000}
            
        try:
            with open(self.my_ini, "r") as f1:
                my_dictini = yaml.safe_load(f1)
        except:
           
           print('Création de intipartner_ini.yaml comme : ', self.my_ini)
           
        
        self.working_dir=my_dictini['working_dir']
        
        
        if 'stack_seuil' in my_dictini :
            self.stack_seuil=my_dictini['stack_seuil']
        else :
            self.stack_seuil=1000    

    
    def save_ini(self) :
        self.my_dictini['lang']=self.langue
        self.my_dictini['working_dir']=self.working_dir
        self.my_dictini['stack_seuil']=self.stack_seuil
        try:
            with open(self.my_ini, "w") as f1:
                yaml.dump(self.my_dictini, f1, sort_keys=False)
                #print(self.my_ini)
        except :
            print (self.tr('Erreur à la sauvegarde de intipartner_ini.yaml : '), self.my_ini)
    
    # fonction non active
    def check_version (self):
        # contact site inti pour nouvelle version
        try :
            reponse = requests.get('http://valerie.desnoux.free.fr/inti/inti_partner_version.html', timeout=10)
            if reponse.status_code == 200 :
                html_text=reponse.text
                pos=html_text.find('Version =')
                v=html_text[pos+10:pos+13]
                print('version : ',v)
                if v != self.version :
                    box=False
                    if box :
                        msg = QMessageBox()
                        msg.setIcon(QMessageBox.Icon.Information)
                        msg.setText(self.tr("Une nouvelle Version est disponible"))
                        msg.setWindowTitle("Inti Partner")
                        msg.exec()
                    # ou alors on met en rouge la version 
                    self.ui.version_label.setStyleSheet('color: red')
        except:
            pass
    
    
    def on_mouse_move (self, pos) :
        
        app_tab= self.ui.tab_main.tabText(self.ui.tab_main.currentIndex())
        #print(app_tab)

        if app_tab=='Stack' :
            if self.ui.stack_image_view.imageItem.sceneBoundingRect().contains(pos) :
                mouse_point= self.ui.stack_image_view.view.mapSceneToView(pos)
                x,y =int(mouse_point.x()), int(mouse_point.y())
                
                if 0 <= x < self.ui.stack_image_view.image.shape[0] and 0<= y < self.ui.stack_image_view.image.shape[1] :
                    # pour affichage premiere ligne n'est pas 0 mais 1
                    msg="x : "+str(x+1)+' , y : '+str(y+1)
                    #print(msg)
                    pix_value = self.ui.stack_image_view.image[x,y]
                    msg=msg+' , I : '+str(int(pix_value))
                    #print(pix_value)
                    self.ui.statusbar.showMessage(msg)
                else:
                    #print ("mouse out of bounds")
                    self.ui.statusbar.clearMessage() 
        if app_tab=='Mosa' :
            if self.ui.mosa_image_view.imageItem.sceneBoundingRect().contains(pos) :
                mouse_point= self.ui.mosa_image_view.view.mapSceneToView(pos)
                x,y =int(mouse_point.x()), int(mouse_point.y())
                
                if 0 <= x < self.ui.mosa_image_view.image.shape[0] and 0<= y < self.ui.mosa_image_view.image.shape[1] :
                    # pour affichage premiere ligne n'est pas 0 mais 1
                    msg="x : "+str(x+1)+' , y : '+str(y+1)
                    #print(msg)
                    pix_value = self.ui.mosa_image_view.image[x,y]
                    try :
                        if len(pix_value) != 1:
                            msg=msg+' , R : '+str(int(pix_value[0]))+ ' , G : '+str(int(pix_value[1]))+' , B : '+str(int(pix_value[2]))
                    except :
                        msg=msg+' , I : '+str(int(pix_value))
                    self.ui.statusbar.showMessage(msg)
                else:
                    #print ("mouse out of bounds")
                    self.ui.statusbar.clearMessage()     
                    
        if app_tab=="Animation" : 
            if self.ui.anim_image_view.imageItem.sceneBoundingRect().contains(pos) :
                mouse_point= self.ui.anim_image_view.view.mapSceneToView(pos)
                x,y =int(mouse_point.x()), int(mouse_point.y())
                msg='X : '+str(x)+' ; Y : '+str(y)
                self.ui.statusbar.showMessage(msg)
                
        if app_tab=='SER' :
            if self.ui.ser_view.imageItem.sceneBoundingRect().contains(pos) :
                mouse_point= self.ui.ser_view.view.mapSceneToView(pos)
                x,y =int(mouse_point.x()), int(mouse_point.y())
                if 0 <= x < self.ui.ser_view.image.shape[1] and 0<= y < self.ui.ser_view.image.shape[2] :
                    #numero de trame
                    trame= self.ui.ser_view.currentIndex
                    msg="x : "+str(x+1)+' , y : '+str(y+1)
                    pix_value = self.ui.ser_view.image[trame][x,y]
                    msg=msg+' , I : '+str(int(pix_value))
                    self.ui.statusbar.showMessage(msg)
                else:
                    self.ui.statusbar.clearMessage()     

                
        if app_tab=='Traitements' or app_tab=="Processings":
            if self.ui.proc_view.imageItem.sceneBoundingRect().contains(pos) :
                mouse_point= self.ui.proc_view.view.mapSceneToView(pos)
                x,y =int(mouse_point.x()), int(mouse_point.y())
                
                if 0 <= x < self.ui.proc_view.image.shape[0] and 0<= y < self.ui.proc_view.image.shape[1] :
                    # pour affichage premiere ligne n'est pas 0 mais 1
                    msg="x : "+str(x+1)+' , y : '+str(y+1)
                    #print(msg)
                    pix_value = self.ui.proc_view.image[x,y]
                    try :
                        if len(pix_value) != 1:
                            msg=msg+' , R : '+str(int(pix_value[0]))+ ' , G : '+str(int(pix_value[1]))+' , B : '+str(int(pix_value[2]))
                    except :
                        msg=msg+' , I : '+str(int(pix_value))
                    self.ui.statusbar.showMessage(msg)
                else:
                    #print ("mouse out of bounds")
                    self.ui.statusbar.clearMessage()  
        if app_tab=='Magnet' :
            if self.ui.mag_img_view.imageItem.sceneBoundingRect().contains(pos) :
                mouse_point= self.ui.proc_view.view.mapSceneToView(pos)
                x,y =int(mouse_point.x()), int(mouse_point.y())
                
                if 0 <= x < self.ui.mag_img_view.image.shape[0] and 0<= y < self.ui.mag_img_view.image.shape[1] :
                    # pour affichage premiere ligne n'est pas 0 mais 1
                    msg="x : "+str(x+1)+' , y : '+str(y+1)
                    #print(msg)
                    pix_value = self.ui.mag_img_view.image[x,y]
                    try :
                        if len(pix_value) != 1:
                            msg=msg+' , R : '+str(int(pix_value[0]))+ ' , G : '+str(int(pix_value[1]))+' , B : '+str(int(pix_value[2]))
                    except :
                        msg=msg+' , I : '+str(int(pix_value))
                    self.ui.statusbar.showMessage(msg)
                else:
                    #print ("mouse out of bounds")
                    self.ui.statusbar.clearMessage()  
                
    def on_mouse_click (self, ev) :
        app_tab= self.ui.tab_main.tabText(self.ui.tab_main.currentIndex())
        #print(app_tab)

        if app_tab=='SER' :
            pos=ev.pos()
            try :
                if self.mypoint.scene() is  self.ui.ser_raw_view.getView().scene() :
                    self.ui.ser_raw_view.view.removeItem(self.mypoint)
            except :
                pass
            if self.ui.ser_view.imageItem.sceneBoundingRect().contains(pos) :
                
                mouse_point= self.ui.ser_view.view.mapSceneToView(pos)
                x,y =int(mouse_point.x()), int(mouse_point.y())
                msg='X : '+str(x)+' ; Y : '+str(y)
                self.ui.statusbar.showMessage(msg)
                self.ui.ser_posx_lbl.setText(str(x))
                if self.flag_raw :
                    # point rouge
                    self.mypoint=QGraphicsEllipseItem(0,0,6,6)
                    self.mypoint.setPen(pg.mkPen(color=(250, 120, 0), width=12))
                    self.mypoint.setPos(self.ui.ser_view.currentIndex-3, x-3)
                    self.ui.ser_raw_view.view.addItem(self.mypoint)  
                
                self.v_bar_pro.setPos(x)
            else:
                #print ("mouse out of bounds")
                self.ui.statusbar.clearMessage() 
    
    #--------------------------------------------------------------------------
    # tab viewer
    #--------------------------------------------------------------------------   
    
    def view_dir_open_clicked (self) :
        select_dir_name = str(QFileDialog.getExistingDirectory(self, self.tr("Sélection répertoire"), self.working_dir))
        if select_dir_name : #si ne retourne pas une chaine vide
            self.working_dir=select_dir_name
            self.ui.view_dir2_lbl.setText(self.working_dir)
            #self.ui.view_dir_lbl.setText(self.working_dir)
            self.ui.select_dir_lbl.setText(self.working_dir)
            self.select_read()
            self.view_radio_clicked()

    
    def view_display_img (self, file_list) :
        self.ui.img_list_view.clear()
        galx=200
        galy=200
        
        for file_name in file_list :
            pro_item=QListWidgetItem()
            ext = self.get_extension(file_name)
                        
            if ext=='png' or ext =='tiff' :
                 
                pix = QtGui.QPixmap(file_name)
                self.pixmap = pix.scaled(galx, galy, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
                    
            if ext == 'fits' :
                mydata, header= self.read_fits_image(file_name)
                h, w = mydata.shape
                mydata=np.array(mydata,dtype='uint16')
                img_8bits= (mydata/256).astype(np.uint8)
                h,w =img_8bits.shape
                img_8bits = np.ascontiguousarray(img_8bits)
                q_img=QtGui.QImage(img_8bits.data, w, h ,w ,QtGui.QImage.Format_Grayscale8).copy()
                #q_img = QtGui.QImage(np.ascontiguousarray(mydata), w, h, QtGui.QImage.Format_Grayscale8)
                #q_img=q_img.convertToFormat(QtGui.QImage.Format_RGB32)
                pix = QtGui.QPixmap.fromImage(q_img)
                self.pixmap = pix.scaled(galx, galy, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
                
            if ext == "ser" :
                scan = Serfile(file_name, False)
                self.FrameCount = scan.getLength()    #      return number of frame in SER file.
                self.ser_hdr = scan.getHeader()
                FrameIndex = self.FrameCount//2  # on prend l'image du milieu de la video comme vignette
                num_raw = scan.readFrameAtPos(FrameIndex)
                mydata=np.flipud(np.rot90(num_raw))
                h, w = mydata.shape
                mydata=np.array(mydata,dtype='uint16')
                img_8bits= (mydata/256).astype(np.uint8)
                h,w =img_8bits.shape
                img_8bits = np.ascontiguousarray(img_8bits)
                q_img=QtGui.QImage(img_8bits.data, w, h ,w ,QtGui.QImage.Format_Grayscale8).copy()
                pix = QtGui.QPixmap.fromImage(q_img)
                self.pixmap = pix.scaled(galx, galy, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
                   

            pro_icon=QtGui.QIcon()
            pro_icon.addPixmap(self.pixmap)
            pro_item.setIcon(pro_icon)
            pro_item.setText(self.short_name(file_name))
            self.ui.img_list_view.addItem(pro_item)
            
        
        self.myscreen_w = self.ui.img_list_view.width()
        h = galy
        w = len(file_list) * (galx+25)
        nh= int( w / self.myscreen_w )
        nw = int(self.myscreen_w/(galx+25))
        nw=min(nw,len(file_list))
        w= nw * (galx+25)+16
        h=(galy+50)*(nh+1)
        self.myimg_solo = img_wnd(self.working_dir)
    
    def view_img_click (self,item) :
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        index= self.ui.img_list_view.row(item)
        self.file_view= self.file_list_view[index]
        ext = self.get_extension(self.file_view)
        
        if ext=='png' or ext=='tiff' :
            img_data=cv2.imread(self.file_view,cv2.IMREAD_UNCHANGED)
            if len(img_data.shape) == 3 :
                img_data=cv2.cvtColor(img_data,cv2.COLOR_BGR2RGB)   
        
        if ext == 'fits' :
            mydata, header= self.read_fits_image(self.file_view)
            h, w = mydata.shape
            img_data=np.array(mydata,dtype='uint16')
        
        if ext == "ser" :
            try:
                scan = Serfile(self.file_view, False)
            
                self.FrameCount = scan.getLength()    #      return number of frame in SER file.
                Width = int(scan.getWidth())          #      return width of a frame
                Height = int(scan.getHeight())       #      return height of a frame
                self.ser_hdr = scan.getHeader()
                
                # forme le volume de data 
                # initialize le tableau qui recevra l'image somme de toutes les trames
                # garde une copie des trames originales si on veut trimmer le fichier
                FrameIndex=0
                Frame_start = self.FrameCount//4
                ser_volume=np.zeros((self.FrameCount,Height, Width),dtype='uint16')
                
                while FrameIndex < self.FrameCount:
                    try :
                        num_raw = scan.readFrameAtPos(FrameIndex)
                        #num=np.flipud(np.rot90(num_raw))
                    except:
                        print(FrameIndex)
        
                    # ajoute la trame au volume
                    ser_volume[FrameIndex]=num_raw
                    #increment la trame et l'offset pour lire trame suivant du fichier .ser
                    FrameIndex=FrameIndex+1
            
            except:
                print(self.tr('Erreur ouverture fichier : ')+self.file_view)
        
        self.myimg_solo.show()
        if ext == "ser" :
            img_proc = ser_volume
        else :
            img_proc = np.fliplr(np.rot90(img_data, 3))
            
        self.myimg_solo.ui.inti_view.setImage(img_proc, autoRange=False)
        if ext == "ser" :
            self.myimg_solo.ui.inti_view.setCurrentIndex(Frame_start)
        self.myimg_solo.set_title(self.short_name(self.file_list_view[index]))
        self.myimg_solo.on_ferme.connect(self.view_open_in_tab)
        self.myimg_solo.ui.raise_()
        self.myimg_solo.ui.activateWindow()      
        
        QApplication.restoreOverrideCursor()

    def view_filtre_clicked (self, pattern) :
        QApplication.setOverrideCursor(Qt.WaitCursor)
        crit_list=[]
        #self.ui.view_dir_lbl.setText(self.working_dir)   
        filtre={"clahe":"*_clahe","protus":"*_protus*","cont":"*_cont","doppler":"*_doppler*","color":"*_color*","free":"*_free","raw":"*_raw","tous":"*","disk":'*_disk'}
        ext = self.view_get_radio()
        critere= filtre[pattern]+ext
        crit_dir = self.working_dir
        crit_list =  fnmatch.filter(os.listdir(crit_dir), critere)
        self.ui.view_dir2_lbl.setText(crit_dir)
        #self.ui.view_dir_lbl.setText(crit_dir)
        
        if not crit_list :
            if filtre[pattern] == "*_clahe" :
                crit_dir = self.working_dir+os.sep+"Clahe"
                crit_list =  fnmatch.filter(os.listdir(crit_dir), critere)
                self.ui.view_dir2_lbl.setText(crit_dir)
            if filtre[pattern] == "*_raw" :
                crit_dir = self.working_dir+os.sep+"Complements"
                crit_list =  fnmatch.filter(os.listdir(crit_dir), critere)
                self.ui.view_dir2_lbl.setText(crit_dir)
        try :
            self.file_list_view = [crit_dir+os.sep+x for x in crit_list]
            self.view_display_img(self.file_list_view)
            self.ui.img_list_view.itemDoubleClicked.connect(self.view_img_click)
            
        except :
            pass
        
        QApplication.restoreOverrideCursor()
        
    def view_get_radio (self) :
        if self.ui.view_png_radio.isChecked() :
            ext = ".png"
            
        elif  self.ui.view_fits_radio.isChecked() :
            ext=".fits"
            
        else :
            if self.ui.view_ser_radio.isChecked() :
                ext=".ser"
            else :
                ext=".tiff"
    
        return ext
    
    def view_radio_clicked(self) :
        if self.ui.view_png_radio.isChecked() :
            self.view_filtre_clicked ('disk')
        else :
            self.view_filtre_clicked ('tous')
        
    
    def view_open_in_tab(self) :
        QApplication.setOverrideCursor(Qt.WaitCursor)
        
        self.ext_view = self.get_extension(self.file_view)
        if self.ext_view == 'png' or self.ext_view == 'fits' or self.ext_view == 'tiff':
            page = self.ui.tab_main.findChild(QWidget, 'tab_proc')
            self.ui.tab_main.setCurrentWidget(page)
            self.file_proc = self.file_view
            self.proc_read()
            self.file_grid=self.file_view
            self.grid_read()
            
        if self.ext_view == 'ser' :
            page = self.ui.tab_main.findChild(QWidget, 'tab_ser')
            self.ui.tab_main.setCurrentWidget(page)
            self.file_ser = self.file_view
            self.ser_read()
        self.myimg_solo.ui.close()
        
        QApplication.restoreOverrideCursor()
        
    
    def view_open_context_menu(self, pos) :
        if self.ui.view_ser_radio.isChecked() :
            item = self.ui.img_list_view.itemAt(pos)
            if not item:
                return  # Pas de fichier sous le clic
            else :
                self.selected_filename = item.text()
                
    
            menu = QMenu(self)
            self.selected_filename = item.text()
            action_chdir = menu.addAction(self.tr("Changer répertoire INTI"))
            action_ouvrir = menu.addAction(self.tr("Ouvrir INTI"))
            action_lancer = menu.addAction(self.tr("Traiter avec INTI"))
    
            action = menu.exec(self.ui.img_list_view.viewport().mapToGlobal(pos))
    
            if action == action_ouvrir:
                self.view_open_inti()
            elif action == action_lancer:
                self.view_run_inti()
            elif action == action_chdir :
                self.view_chdir_inti()

    def view_chdir_inti(self) :
        inti_exe, _ = QFileDialog.getOpenFileName(self, "Trouver executable inti", "", "inti (inti*.exe)")
        if inti_exe:
            self.inti_dir = os.path.dirname(inti_exe)
            print(self.tr("Répertoire d'inti' :"), self.inti_dir)
            
    def view_open_inti(self) :
        QApplication.setOverrideCursor(Qt.WaitCursor)
        filename=self.selected_filename
        filename=self.working_dir+os.sep+filename
        #print("fichier : "+ filename)
        
        if not os.path.exists(self.inti_dir+os.sep+'inti.exe'):
            inti_exe, _ = QFileDialog.getOpenFileName(self, "Trouver executable inti", "", "inti (inti*.exe)")
            if inti_exe:
                self.inti_dir = os.path.dirname(inti_exe)
                print(self.tr("Répertoire d'inti' :"), self.inti_dir)
        else :
            try :
                if 'spyder' in sys.modules :
                    print("lance inti")
                else :
                    subprocess.Popen([self.inti_dir+os.sep+'inti.exe', filename])
            except :
                print(self.tr('ERREUR :  lancement '+ self.inti_dir+os.sep+'inti.exe'))
        
        QApplication.restoreOverrideCursor()
        
    def view_run_inti(self) :
        QApplication.setOverrideCursor(Qt.WaitCursor)
        filename=self.selected_filename
        filename=self.working_dir+os.sep+filename
        # lance inti et traite
        if not os.path.exists(self.inti_dir+os.sep+'inti.exe'):
            inti_exe, _ = QFileDialog.getOpenFileName(self, "Trouver executable inti", "", "inti (inti*.exe)")
            if inti_exe:
                self.inti_dir = os.path.dirname(inti_exe)
                print("Répertoire d'inti' :", self.inti_dir)
        else :
            try :
                if 'spyder' in sys.modules :
                    print("lance inti")
                else :
                    subprocess.Popen([self.inti_dir+os.sep+'inti.exe', filename, "True"])
            except :
                print(self.tr('ERREUR :  lancement '+ self.inti_dir+os.sep+'inti.exe'))
        
        QApplication.restoreOverrideCursor()
        
    #--------------------------------------------------------------------------
    # tab stack
    #--------------------------------------------------------------------------
    def stack_img_list_open_clicked (self):
        # choix de ne traiter que les images png noir et blanc > ben non on ajoute le fits !
        self.stack_dir=self.working_dir
        file_list=[]
        self.file_list=[]
        self.ui.stack_image_view.clear()
        #file_list = QFileDialog.getOpenFileNames(self, "Selectionner Imges", self.stack_dir, "Fichiers png (*.png);; Fichiers FITS (*.fits *.fit);;Tous les fichiers (*)")
        file_list = QFileDialog.getOpenFileNames(self,self.tr( "Selectionner Images"), self.stack_dir, self.tr("Fichiers png (*.png);;Fichiers disk png (*_disk.png);;Fichiers clahe png (*_clahe.png);;Fichiers free (*_free.png);;Fichiers recon fits (*_recon.fits);;Fichiers free fits (*_free.fits);;Fichiers fits (*.fits)"), self.pattern)
        self.pattern = file_list[1]
        
        if len(file_list[0]) !=0  :
            
            self.ui.stack_list.clear()
            self.file_list=file_list[0]
            self.ext_stack= self.get_extension (self.file_list[0])
            self.working_dir= self.get_dirpath(self.file_list[0])
            self.ui.stack_dir_lbl.setText(self.working_dir)
            self.load_imagettes ()
            file_names=[]
            for f in self.file_list :
                file_names.append (self.short_name(f))
            self.ui.stack_list.addItems (file_names)
            self.ui.stack_image_view.ui.histogram.hide()
            
            self.ui.stack_list.setCurrentRow(0)
            self.ui.stack_list.item(0).setSelected(True)
    
            self.ui.stack_img_list_view.setFocus()
            self.ui.stack_img_list_view.setCurrentRow(0)
        
        
    
    def load_imagettes(self) :
        galx=100
        galy=100
        ext = self.check_extension (self.file_list)
        flag_error = False
        my_file_list = self.file_list.copy()
        if ext != '' :
            try :
                page = self.ui.tab_main.findChild(QWidget, 'tab_stack')
                self.ui.stack_img_list_view.clear()
                #self.ui.img_list_view.setViewMode(QtGui.QListView.IconMode)
                self.ui.tab_main.setCurrentWidget(page)
                
                for file_name in my_file_list:
                    flag_error = False
                    pro_item=QListWidgetItem()
                    
                    # recupère data et transforme en Qpixmap suivant png, jpg ou fits
                    if ext=='png' or ext=='jpg':
                        # 
                        pix = QtGui.QPixmap(file_name)
                        if pix.toImage().isGrayscale() :
                            self.pixmap = pix.scaled(galx, galy, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
                        else :
                            print("Error " +file_name + self.tr(" : Image couleur"))
                            flag_error= True
                            # il faut retirer l'image couleur...
                            self.file_list.remove(file_name)
                    
                    if ext == 'fits' :
                        # code correct 
                        data, header= self.read_fits_image(file_name)
                        data = data.astype(np.int16)
                        h, w = data.shape
                        q_img = QtGui.QImage(np.ascontiguousarray(data), w, h, QtGui.QImage.Format_Grayscale16)
                        pix = QtGui.QPixmap.fromImage(q_img)
                        self.pixmap = pix.scaled(galx, galy, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
                        
                    if not flag_error :    
                        pro_icon=QtGui.QIcon()
                        pro_icon.addPixmap(self.pixmap)
                        pro_item.setIcon(pro_icon)
                        pro_item.setText(self.short_name(file_name))
                        self.ui.stack_img_list_view.addItem(pro_item)
                        
                
                    
            except:
                pass
        
    def check_extension(self, file_list) :
        ext=''
        for f in file_list :
            e=f.split('.')[-1]
            if ext=='' :
                ext=e
            if e != ext :
                print(self.tr("fichier : "), f, self.tr("extension inconsistent"))
                ext=''
                break
        return ext
    
    def run_stack_clicked(self):
        # cette version dedistord-SUNSCAN ne gère que les fichiers png
        self.file_result=[]
        self.file_name_result=[]
        self.ui.stack_list_result.clear()
        path= self.working_dir+os.sep
        fileref= self.file_list[0]
        self.file_result.append(fileref)
        self.file_name_result.append(self.short_name(fileref))
        #t0=time.time()
        self.ui.stack_progress_bar.setMaximum(len(self.file_list)-1)
        self.ui.stack_progress_bar.setVisible(True)
        
        if self.ui.stack_noalign_checkbox.isChecked() :
            if self.ext_stack == 'png' :
                sum_image = cv2.imread(fileref,cv2.IMREAD_UNCHANGED) # on récupère de format des images et on sauvegarde la première
            if self.ext_stack== 'fits':
                sum_image, hdr = self.read_fits_image(fileref)
            sum_image = sum_image.astype(np.uint32)  # conversion en 32 bits
             
            for i in range(1, len(self.file_list)) :
                self.ui.stack_progress_bar.setValue(i)
                
                if self.ext_stack == 'png' :
                    im=cv2.imread(self.file_list[i], cv2.IMREAD_UNCHANGED) 
                if self.ext_stack== 'fits':
                    im, hdr = self.read_fits_image(self.file_list[i])
                
                sum_image=sum_image+im
            
            sum_image_second=sum_image
            
        else :
            if self.ext_stack=='png' :
                print("start dedistord...", flush=True)
                # Initialisation du stacking
                sum_image = cv2.imread(fileref,cv2.IMREAD_UNCHANGED) # on récupère de format des images et on sauvegarde la première
                sum_image = sum_image.astype(np.uint32)  # conversion en 32 bits           
                
                seq_abort=False
                seq_error=False
                second_file_list=[]
                
                # check si une seconde série est à calculer et vérifie que les images sont présentes
                second_pattern=str(self.ui.stack_second_combo.currentText())
                if second_pattern != 'None' :
                    for i in range (len(self.file_list)) :
                        suffixe = '_disk.'
                        dir_second =self.working_dir
                        if self.file_list[i].find(suffixe) == -1 :
                            suffixe ="_clahe."
                            dir_second = os.path.dirname(self.working_dir)
                        root=self.short_name(self.file_list[i]).split(suffixe)[0]
                        postfix= '_'+ second_pattern.lower()+'.png'
                        pattern=root+"*"+postfix
                        second_file_found = fnmatch.filter(os.listdir(dir_second), pattern)
                        
                        if len(second_file_found) == 0 :
                            print(self.tr('Fichier ')+ pattern +self.tr(' non trouvé'))
                            seq_error=True
                        else :
                            second_file_list.append(dir_second+os.sep+second_file_found[0])
                            #print(dir_second+os.sep+second_file_found[0])
                    if not seq_error :
                        # Initialisation du stacking
                        sum_image_second = cv2.imread(second_file_list[0],cv2.IMREAD_UNCHANGED) # on récupère de format des images et on sauvegarde la première
                        sum_image_second = sum_image_second.astype(np.uint32)  # conversion en 32 bits
                    else :
                        second_file_list =self.file_list
                        sum_image_second=sum_image
                else :
                    second_file_list =self.file_list
                    sum_image_second=sum_image
                        
                        
                if not seq_abort :
                    
                    # flag sunscan si sunscan dans le nom...
                    p=self.file_list[0].rfind('sunscan')
                    if p != -1 :             
                        print("Sunscan images")
                        thresh=0
                    else :
                        thresh=self.stack_seuil
                    
                    for i in range(0, len(self.file_list)) :
                        self.ui.stack_progress_bar.setValue(i)
                        # Calcul des cartes de décalage
                        # patch_size : taille du patch de cross-corrélation
                        # step_size : pas de cross-corrélation (en X et Y)
                        # intensity_threshold : seuil d'intensité en dessous duquel la corrélation n'est pas calculé
                        
                        
                        #dx_map, dy_map, amplitude_map = ddist.find_distorsion(path, fileref, self.file_list[i], patch_size=64, step_size=20, intensity_threshold=0)  # was 1000
                        # : patch_size=32, step_size=10, intensity_threshold=0 Version CB sunscan
                        
                        patch_size=int(self.ui.stack_patch_text.text())
                        step_size=int(patch_size/2.5)
                        #print(patch_size, step_size)
                        dx_map, dy_map, amplitude_map = ddist.find_distorsion(path, fileref, self.file_list[i], patch_size, step_size, intensity_threshold=thresh)
                        # Correction des distorsions dans la séquence principale (format PNG en entrée)
                        corrected_image = ddist.correct_image_png(path, self.file_list[i], dx_map, dy_map)
                        
                        # Correction des distorsions dans la séquence secondaire (format PNG en entrée)
                        corrected_image_second = ddist.correct_image_png(path, second_file_list[i], dx_map, dy_map)
                        
                        # sauvegarde des images unitaires dans un repertoire stack 
                        self.stack_dir = self.working_dir+os.sep+'Stack'
                        if not os.path.isdir(self.stack_dir):
                           os.makedirs(self.stack_dir)

                        fname= self.stack_dir+os.sep+'st'+self.short_name(self.file_list[i])
                        cv2.imwrite(fname,corrected_image)
                        if second_pattern != 'None' :
                            fname_second=self.stack_dir+os.sep+'st'+self.short_name(second_file_list[i])
                            cv2.imwrite(fname_second,corrected_image_second)
                        
                        # Sommation (stacking)
                        if i > 1:
                            sum_image = sum_image + corrected_image.astype(np.uint32)
                            sum_image_second = sum_image_second + corrected_image_second.astype(np.uint32)
                            
                        print(self.short_name(self.file_list[i])+" deformed", flush=True)
            else :
                print("stacking on fits pas encore implementé")
                return

        self.ui.stack_progress_bar.setVisible(False)
        #t1=time.time()
        #print(t1-t0, flush=True)

        if self.ui.stack_noalign_checkbox.isChecked() :
            im16=sum_image
            im16_second =sum_image_second
        else :
            # Normalisation sur 16 bits
            number_image=len(self.file_list)
            sum_image = sum_image / number_image
            #image_eclipse=sum_image
            im16 = sum_image.astype(np.uint16)
            sum_image_second = sum_image_second / number_image
            im16_second = sum_image_second.astype(np.uint16)
        
        # sauve image stackked
        f0=self.short_name(self.file_list[0]).split('.')[0]
        f1=self.short_name(self.file_list[-1]).split('.')[0][1:]
        root_name=f0+'-'+ f1
        file_corrected=self.working_dir+os.sep+root_name+'_stack.fits'
        fits.writeto(file_corrected, im16, overwrite=True)
        im16=im16.astype(np.uint16)
        cv2.imwrite(self.working_dir+os.sep+root_name+'_stack.png', im16)
        self.file_result.append(self.working_dir+os.sep+root_name+'_stack.png')
        self.file_name_result.append(root_name+'_stack.png')
        #print("Result stackking : ", file_corrected)
        
        # image stackée eclipse virtuelle
        # decode le fichier log pour xc, yc, radius, y1,y2,x1,x2
        # ajout test sur sunscan pour nommage
        fileref_short = self.short_name(fileref)
        if fileref_short.find('sunscan')!= -1 :
            fileref_short=fileref_short.replace('sunscan', '_scan')
        
        """
        baseline = os.path.basename(get_baseline(os.path.splitext(fileref_short)[0]))
        file_log=self.working_dir+os.sep+baseline+"_log.txt"
        
        if not os.path.exists(file_log):
            # remonte d'un cran le chemin
            parent_path = Path(self.working_dir).parent
            file_log=str(parent_path)+os.sep+baseline+"_log.txt"
       
        cx,cy,sr,ay1,ay2,ax1,ax2 = mo.decode_log(file_log)
        
        if sr != 0 : 
            image_eclipse=image_eclipse*2
            image_eclipse = ddist.make_eclipse_effect(image_eclipse, int(int(sr)*1.011)*2, int(cx), int(cy))
            
            # sauve image eclipse
            image_eclipse=np.array(image_eclipse, dtype="uint16")
            file_corrected=self.working_dir+os.sep+root_name+'_stack_protus.fits'
            fits.writeto(file_corrected, image_eclipse, overwrite=True)
            cv2.imwrite(self.working_dir+os.sep+root_name+'_stack_protus.png', image_eclipse)
            self.file_result.append(self.working_dir+os.sep+root_name+'_stack_protus.png')
            self.file_name_result.append(root_name+'_stack_protus.png')
        else :
            print(self.tr("Pas de fichier _log.txt pour image des protubérances"))
        """ 
        # calcul image sharp
        if self.ui.stack_sharplow_radio.isChecked() :
            self.sharp_level=1 
        else:
            self.sharp_level=3 
        im_sharp=self.sharpenImage(im16, self.sharp_level)
        ims=np.array(im_sharp, dtype="uint16")
        
        # sauve image sharp
        file_corrected=self.working_dir+os.sep+root_name+'_stack_sharp.fits'
        fits.writeto(file_corrected, ims, overwrite=True)
        cv2.imwrite(self.working_dir+os.sep+root_name+'_stack_sharp.png', im16)
        self.file_result.append(self.working_dir+os.sep+root_name+'_stack_sharp.png')
        self.file_name_result.append(root_name+'_stack_sharp.png')
            
            
        if not self.ui.stack_noalign_checkbox.isChecked() :
            if second_pattern != 'None' and not seq_error :
                self.file_result.append(second_file_list[0])
                self.file_name_result.append(self.short_name(second_file_list[0]))
                # sauve second image stackked
                file_corrected=self.working_dir+os.sep+root_name+'_stack_second.fits'
                fits.writeto(file_corrected, im16_second, overwrite=True)
                cv2.imwrite(self.working_dir+os.sep+root_name+'_stack_second.png', im16_second)
                self.file_result.append(self.working_dir+os.sep+root_name+'_stack_second.png')
                self.file_name_result.append(root_name+'_stack_second.png')
                #print("Result stackking second : ", file_corrected)
                
                # calcul image sharp
                im_sharp_second=self.sharpenImage(im16_second, self.sharp_level)
                ims=np.array(im_sharp_second, dtype="uint16")
                
                # sauve image sharp
                file_corrected=self.working_dir+os.sep+root_name+'_stack_second_sharp.fits'
                fits.writeto(file_corrected, ims, overwrite=True)
                cv2.imwrite(self.working_dir+os.sep+root_name+'_stack_second_sharp.png', im16_second)
                self.file_result.append(self.working_dir+os.sep+root_name+'_stack_second_sharp.png')
                self.file_name_result.append(root_name+'_stack_second_sharp.png')
        
        
        self.ui.stack_list_result.addItems(self.file_name_result)
        self.ui.stack_image_view.clear()
        self.display_stack_image_fits (file_corrected)
        self.ui.stack_image_view.ui.histogram.show()
        self.ui.stack_list_result.setCurrentRow(len(self.file_name_result)-1)
        
        
        
    def stack_list_result_clicked(self) :
        index=self.ui.stack_list_result.currentRow()
        #print (self.file_result[index])
        #self.ui.stack_img_list_view.setCurrentRow(index)
        
        ext = self.get_extension (self.file_result[index])
        if ext == 'fits' :
            self.display_stack_image_fits (self.file_result[index])
        if ext == 'png' or ext=='jpg' :
            self.display_stack_image_png (self.file_result[index])
        
        
    def stack_list_clicked(self) :
        index=self.ui.stack_list.currentRow()
        #print (self.file_list[index])
        self.ui.stack_img_list_view.setCurrentRow(index)
        
        ext = self.get_extension (self.file_list[index])
        if ext == 'fits' :
            self.display_stack_image_fits (self.file_list[index])
        if ext == 'png' or ext=='jpg' :
            self.display_stack_image_png (self.file_list[index])
        self.ui.stack_image_view.ui.histogram.hide()
        
    def stack_remove_item(self):
        index=self.ui.stack_list.currentRow()
        self.ui.stack_list.takeItem(index)      
        self.ui.stack_img_list_view.takeItem(index)
        del self.file_list[index]
        self.ui.stack_image_view.clear()
        self.stack_img_list_view_sel_changed()
        
        
    def stack_img_list_view_sel_changed (self) :
        index=self.ui.stack_img_list_view.currentRow()
        #print(self.short_name(self.file_list[index]))
        if index !=-1 :
            ext = self.get_extension (self.file_list[index])
            if ext == 'fits' :
                self.display_stack_image_fits (self.file_list[index])
            if ext == 'png' or ext=='jpg' :
                self.display_stack_image_png (self.file_list[index])
            self.ui.stack_image_view.ui.histogram.show()
            
            try :
                self.ui.stack_list.setCurrentRow(index)
                self.ui.stack_list.item(index).setSelected(True)
            except :
                pass
   
    def stack_flip_hb (self) :
        img=self.ui.stack_image_view.image
        flip_img= cv2.flip(img,1)
        self.ui.stack_image_view.setImage(flip_img, autoRange=False)
        rot_data = np.fliplr(np.rot90(flip_img, 3))
        cv2.imwrite(self.file_list[self.ui.stack_img_list_view.currentRow()], rot_data)
        print(self.file_list[self.ui.stack_img_list_view.currentRow()]+self.tr(' enregistré'))
        
    def stack_flip_dg (self) :
        img=self.ui.stack_image_view.image
        flip_img= cv2.flip(img,0)
        self.ui.stack_image_view.setImage(flip_img, autoRange=False)
        rot_data = np.fliplr(np.rot90(flip_img, 3))
        cv2.imwrite(self.file_list[self.ui.stack_img_list_view.currentRow()], rot_data)
        print(self.file_list[self.ui.stack_img_list_view.currentRow()]+self.tr(' enregistré')            )
   
    def stack_open_sel_list(self) :
        self.file_list=[]
        self.ui.stack_dir_lbl.setText(self.working_dir)
        file_name, _ = QFileDialog.getOpenFileName(self, self.tr("Ouvrir une liste de fichier"), self.working_dir, self.tr("Fichiers liste (t*_sel.txt)"))      
        # get directory out of file_name
        self.working_dir, _= os.path.split(file_name)
        #print(self.working_dir)
        if file_name :
            with open(file_name) as f:
                read_lines=f.readlines()
                n=[self.working_dir+os.sep+a.split("\n")[0] for a in read_lines]
                #print(n)
                if read_lines :
                    self.file_list=n
                    self.load_imagettes ()
                    file_names=[]
                    for f in self.file_list :
                        file_names.append (self.short_name(f))
                    self.ui.stack_list.addItems (file_names)
                    self.ui.stack_image_view.ui.histogram.hide()
                    
                    self.ui.stack_list.setCurrentRow(0)
                    self.ui.stack_list.item(0).setSelected(True)

                    self.ui.stack_img_list_view.setFocus()
                    self.ui.stack_img_list_view.setCurrentRow(0)
    
    def stack_save_list (self) :
        mylog=[]
        # construit la liste en texte
        for i in range(self.ui.stack_list.count()) :
            it=self.ui.stack_list.item(i)
            mylog.append(it.text()+'\n')
        with  open(self.working_dir+os.sep+"t"+str(int(time.time()))+'_sel.txt', "w") as logfile:
                logfile.writelines(mylog)
        
    def display_stack_image_png(self, file_name) :
        image_data= cv2.imread(file_name,cv2.IMREAD_UNCHANGED)
        rotated_data = np.fliplr(np.rot90(image_data, 3))
        self.ui.stack_image_view.setImage(rotated_data,autoRange=False, autoLevels=True)
        
    def display_stack_image_fits(self, file_name) :
        image_data, header=self.read_fits_image(file_name)
        image_data=np.flipud(image_data)
        rotated_data = np.fliplr(np.rot90(image_data, 3))
        self.ui.stack_image_view.setImage(rotated_data,autoRange=False, autoLevels=True)
    
    
                
    def sharpenImage(self,image, level):
        """
        Apply multiple sharpening operations to an image.
        Attention image sur 8 bits
    
        Args:
            image (numpy.ndarray): Input image.
    
        Returns:
            numpy.ndarray: Sharpened image.
        """
        
        if level == 1 :
            # Apply Gaussian blur with a 9x9 kernel and sigma of 10.0
            gaussian_3 = cv2.GaussianBlur(image, (0,0), 10.0) # kernel size was (9,9)
            # Sharpen the image by subtracting the blurred image
            image = cv2.addWeighted(image, 1.25, gaussian_3, -0.25, 0, image)
            # Apply Gaussian blur with a 3x3 kernel and sigma of 8.0
            gaussian_3 = cv2.GaussianBlur(image, (0,0),2.0) # was
            # Sharpen the image one more time
            image = cv2.addWeighted(image, 1.5, gaussian_3, -0.5, 0, image)
        
        if level == 2 :
            # Apply Gaussian blur with a 9x9 kernel and sigma of 10.0
            gaussian_3 = cv2.GaussianBlur(image, (0,0), 10.0) # kernel size was (9,9)
            # Sharpen the image by subtracting the blurred image
            image = cv2.addWeighted(image, 1.5, gaussian_3, -0.5, 0, image)
            # Apply Gaussian blur with a 3x3 kernel and sigma of 8.0
            gaussian_3 = cv2.GaussianBlur(image, (0,0),2.0) # was
            # Sharpen the image one more time
            image = cv2.addWeighted(image, 1.5, gaussian_3, -0.5, 0, image)
        
        if level == 3 : 
            
            # Apply Gaussian blur with a 9x9 kernel and sigma of 10.0
            gaussian_3 = cv2.GaussianBlur(image, (0,0), 10.0) # kernel size was (9,9)
            # Sharpen the image by subtracting the blurred image
            image = cv2.addWeighted(image, 1.5, gaussian_3, -0.5, 0, image)
            # Apply Gaussian blur with a 3x3 kernel and sigma of 8.0
            gaussian_3 = cv2.GaussianBlur(image, (0,0),2.0) # was
            # Sharpen the image one more time
            image = cv2.addWeighted(image, 2, gaussian_3, -1, 0, image)
            #
            #gaussian_3 = cv2.GaussianBlur(image, (0,0),4.0) # was
            # Sharpen the image one more time
            #image = cv2.addWeighted(image, 1.5, gaussian_3, -0.5, 0, image)
            
        return image
    
    
    def claheImage(self,image, level):
        """
        Apply clahe processing
        """
        if level == 1 :
            tile =(2,2)
            clip = 0.8 # inti 6.4
        
        if level == 2 : 
            tile = (2,2)
            clip = 2
            
        if level == 3 : 
            tile = (3,3)
            clip = 3
            
        if len(image.shape) !=3 :
            clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=tile) # cliplimit was 0.8
            image = clahe.apply(image)
        else :
            # Conversion en espace LAB (Luminance + Chrominance)
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            # Séparation des canaux
            l, a, b = cv2.split(lab)
            # Création de l'objet CLAHE
            clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=tile)
            # Application sur le canal L (luminance)
            l_clahe = clahe.apply(l)
            # Recomposition de l'image LAB avec L modifié
            lab_clahe = cv2.merge((l_clahe, a, b))
            # Re-conversion en BGR
            image = cv2.cvtColor(lab_clahe, cv2.COLOR_LAB2BGR)
        
            
        return image

   
    # quality factor based on laplacian
    def img_variance(self,myfile) :
    # https://pyimagesearch.com/2015/09/07/blur-detection-with-opencv/
        try :
            ext = self.get_extension (myfile)
            var=0
            if ext == 'png' or ext=='jpg' :
                img = cv2.imread(myfile,cv2.IMREAD_UNCHANGED)
    
            if ext=='fits' :
                img, hdr = self.read_fits_image(myfile)
               
            cx=img.shape[1]//2
            cy=img.shape[0]//2
            
            img2=img[cy-200:cy+200,cx-200:cx+200]

            img2=cv2.medianBlur(img2, 5)
            #plt.imshow(img)
            #plt.show()

            dst= cv2.Laplacian(img2, cv2.CV_64F,3)
            var=dst.var() ** (1/2)
            
        except :
            var=-1
        return int(var)
    
    #--------------------------------------------------------------------------
    # tab selector
    #--------------------------------------------------------------------------
    
    def select_open_dir_clicked (self) :
        self.ui.select_list_files.clear()
        self.ui.select_files_sel_list.clear()
        self.iqm_list=[]
        self.selected_files=[]
        select_dir_name = str(QFileDialog.getExistingDirectory(self, self.tr("Sélection répertoire"), self.working_dir))
        if select_dir_name : #si ne retourne pas une chaine vide
            self.working_dir=select_dir_name
            self.ui.select_dir_lbl.setText(self.working_dir)
            #self.ui.view_dir_lbl.setText(self.working_dir)
            self.ui.view_dir2_lbl.setText(self.working_dir)
            self.select_read() 
            self.ui.img_list_view.clear()
    
    def select_read (self):
        
        self.pattern=self.ui.select_pattern_combo.currentText()
        self.select_files=fnmatch.filter(os.listdir(self.working_dir), self.pattern) # ce sont les short name
        
        # affiche les fichiers du pattern dans liste
        if self.select_files :
            self.refresh_select_list()
            
            
    def select_pattern_clicked (self) :
        self.select_pattern=self.ui.select_pattern_combo.currentText()
        self.ui.select_list_files.clear()
        self.ui.select_files_sel_list.clear()
        self.iqm_list=[]
        try :
            self.select_files=fnmatch.filter(os.listdir(self.working_dir), self.select_pattern) # ce sont les short name
            if self.select_files : 
                self.refresh_select_list()
        except :
            pass
    
    
    def refresh_select_list(self):
        self.ui.select_list_files.addItems(self.select_files)
        
        # affiche les deux premières images de la liste
        self.display_select_image_png(self.select_files[0], viewport=0)
        self.ref_index=0
        self.display_select_image_png(self.select_files[1], viewport=1)
        self.current_index = 1
        self.ui.select_list_files.setCurrentRow(self.current_index)
        self.ui.select_list_files.item(1).setSelected(True)
        #print('current index : ', self.ui.select_list_files.currentRow())
        
        
        # lie les deux vues
        self.ui.select_image_view_ref.view.setXLink(self.ui.select_image_view.view)
        self.ui.select_image_view_ref.view.setYLink(self.ui.select_image_view.view)
        self.ui.select_image_view.view.setXLink(self.ui.select_image_view_ref.view)
        self.ui.select_image_view.view.setYLink(self.ui.select_image_view_ref.view)
        
        
        # calcul list des iqm
        for f in self.select_files :
            iqm=self.img_variance(self.working_dir+os.sep+f)
            self.iqm_list.append([str(iqm), f])
        
        self.ui.select_filesel_lbl.setText(self.select_files[1]+' '+self.iqm_list[1][0])
        self.ui.select_file_lbl.setText(self.select_files[0]+' '+self.iqm_list[0][0])
        
        # se place en viewall mais il faut attendre que l'image se charge dans cycle Qt
        QTimer.singleShot(10, lambda: self.ui.select_image_view_ref.getView().autoRange())

            
    def display_select_image_png(self, file_sh_name, viewport) :
        file_name=self.working_dir+os.sep+file_sh_name
        image_data= cv2.imread(file_name,cv2.IMREAD_UNCHANGED)
        rotated_data = np.fliplr(np.rot90(image_data, 3))
        if viewport==0 :
            self.ui.select_image_view_ref.setImage(rotated_data,autoRange=False, autoLevels=True)
        else :
            self.ui.select_image_view.setImage(rotated_data,autoRange=False, autoLevels=True)
    
    def select_ref_clicked(self) :
       index=self.current_index
       self.ref_index=index
       self.display_select_image_png(self.select_files[index], viewport=0)
       #self.ui.select_files_sel_list.addItem(self.select_files[index])
       self.ui.select_file_lbl.setText(self.select_files[index]+' '+self.iqm_list[index][0])
        
    def select_log_clicked(self):
        index=self.current_index
        if not(self.select_files[index] in self.selected_files)  :
            self.ui.select_files_sel_list.addItem(self.select_files[index])
            self.selected_files.append(self.select_files[index])
        
    def select_next_clicked(self):
        index=self.current_index+1 
        if index < len(self.select_files) :
            self.display_select_image_png(self.select_files[index], viewport=1)
            self.current_index=index
            self.ui.select_filesel_lbl.setText(self.select_files[index]+' '+self.iqm_list[index][0]) 
            self.ui.select_list_files.item(index).setSelected(True)
            
    def select_prev_dir_clicked(self):
        index=self.current_index-1 
        if index >=0 :
            self.display_select_image_png(self.select_files[index], viewport=1)
            self.current_index=index
            self.ui.select_filesel_lbl.setText(self.select_files[index]+' '+self.iqm_list[index][0])
            self.ui.select_list_files.item(index).setSelected(True)
            
    def select_remove_clicked(self):
        #index=self.ui.select_list_files.currentRow()
        index=self.current_index
        self.ui.select_list_files.item(index).setSelected(True)
        self.ui.select_list_files.takeItem(index)
        #self.ui.stack_img_list_view.takeItem(index)
        del self.select_files[index]
        del self.iqm_list[index]
        self.ui.select_image_view.clear()
        #
        new_index=index
        #print('new_index : ', new_index)
        self.ui.select_list_files.item(new_index).setSelected(True)
        if new_index != self.ref_index :
            self.display_select_image_png(self.select_files[new_index], viewport=1)
        else :
            self.display_select_image_png(self.select_files[new_index], viewport=0)
            self.display_select_image_png(self.select_files[new_index], viewport=1)
        self.ui.select_filesel_lbl.setText(self.select_files[new_index]+' '+self.iqm_list[new_index][0])
        
    def select_file_item_clicked(self) :
        index=self.ui.select_list_files.currentRow()
        self.display_select_image_png(self.select_files[index], viewport=1)
        self.current_index=index
        self.ui.select_filesel_lbl.setText(self.select_files[index]+' '+self.iqm_list[index][0])
        
    def select_selfile_item_clicked(self):
        f_name=self.ui.select_files_sel_list.currentItem().text()
        item=self.ui.select_list_files.findItems(f_name,Qt.MatchExactly)
        index_model=self.ui.select_list_files.indexFromItem(item[0])
        index=index_model.row()
        self.ui.select_list_files.setCurrentRow(index)
        self.ui.select_list_files.item(index).setSelected(True)
        self.current_index=index
        self.display_select_image_png(self.select_files[index], viewport=1)
        #print("click : ", self.select_files[index])
        self.ui.select_filesel_lbl.setText(self.select_files[index]+' '+self.iqm_list[index][0])
        
    def sort_files_IQ (self):
        # tableau facteur de qualité,fichier et liste fichier classés
        # BUG fix reaffiche tous les items meme apres un remove
        files_sorted=[]
        self.select_files.clear()
        # classe les fichiers par ordre decroissant sur facteur de qualité
        self.iqm_list.sort(reverse=True)
        files_sorted = [a[1] for a in self.iqm_list]
        self.select_files = files_sorted
        self.ui.select_list_files.clear()
        self.ui.select_list_files.addItems(self.select_files)
        # affiche les deux premières images de la liste
        self.display_select_image_png(self.select_files[0], viewport=0)
        self.display_select_image_png(self.select_files[1], viewport=1)
        self.current_index = 1
        self.ui.select_list_files.item(1).setSelected(True)
        self.ui.select_filesel_lbl.setText(self.select_files[1]+' '+self.iqm_list[1][0])
        self.ui.select_file_lbl.setText(self.select_files[0]+' '+self.iqm_list[0][0])
        
    def sort_files_name (self) :
        # tri par nom de fichier
        self.ui.select_list_files.clear()
        self.ui.select_files_sel_list.clear()
        self.iqm_list=[]
        try :
            self.select_files=fnmatch.filter(os.listdir(self.working_dir), self.select_pattern) # ce sont les short name
            if self.select_files : 
                self.refresh_select_list()
        except :
            pass
        
    def select_new_base (self) :
        # repropose le tri a partir de la liste selectionnée
        if self.ui.select_files_sel_list.count() != 0 :
            self.select_files=[]
            self.ui.select_list_files.clear()
            self.iqm_list=[]
            for i in range(self.ui.select_files_sel_list.count()) :
                self.select_files.append(self.ui.select_files_sel_list.item(i).text())
            self.refresh_select_list()
        
    def select_open_list (self) :
        # ouvre un fichier liste qui contient des noms de fichiers
        self.select_files=[]
        self.ui.select_list_files.clear()
        self.ui.select_dir_lbl.setText(self.working_dir)
        file_name, _ = QFileDialog.getOpenFileName(self,self.tr("Ouvrir une liste de fichier"), self.working_dir, self.tr("Fichiers liste (t*_sel.txt)") )     
        # get directory out of file_name
        self.working_dir, _= os.path.split(file_name)
        #print(self.working_dir)
        if file_name :
            with open(file_name) as f:
                read_lines=f.readlines()
                n=[a.split("\n")[0] for a in read_lines]
                #print(n)
                if read_lines :
                    self.select_files=n
                    self.refresh_select_list()
    
    def select_save_list (self) :
        # sauve la liste des fichiers selectionnés
        mylog=[]
        # construit la liste en texte
        for i in range(self.ui.select_files_sel_list.count()) :
            it=self.ui.select_files_sel_list.item(i)
            mylog.append(it.text()+'\n')
        with  open(self.working_dir+os.sep+"t"+str(int(time.time()))+'_sel.txt', "w") as logfile:
                logfile.writelines(mylog)
        
    def select_clear_sel (self):
        self.ui.select_files_sel_list.clear()
        
    def select_flip_hb (self) :
        img=self.ui.select_image_view.image
        flip_img= cv2.flip(img,1)
        self.ui.select_image_view.setImage(flip_img, autoRange=False)
        rot_data = np.fliplr(np.rot90(flip_img, 3))
        cv2.imwrite(self.working_dir+os.sep+self.select_files[self.current_index], rot_data)
        #print(self.select_files[self.current_index]+' saved')
        
    def select_flip_dg (self) :
        img=self.ui.select_image_view.image
        flip_img= cv2.flip(img,0)
        self.ui.select_image_view.setImage(flip_img, autoRange=False)
        rot_data = np.fliplr(np.rot90(flip_img, 3))
        cv2.imwrite(self.working_dir+os.sep+self.select_files[self.current_index], rot_data)
        #print(self.select_files[self.current_index]+' saved')
        
    #--------------------------------------------------------------------------
    # tab mosa
    #--------------------------------------------------------------------------
    def mosa_img_open_clicked (self):
        self.mosa_dir=self.working_dir
        file_list=[]
        self.ui.mosa_image_view.clear()
        #file_list = QFileDialog.getOpenFileNames(self, "Selectionner Imges", self.stack_dir, "Fichiers png (*.png);; Fichiers FITS (*.fits *.fit);;Tous les fichiers (*)")
        file_list = QFileDialog.getOpenFileNames(self, self.tr("Selectionner Images"), self.mosa_dir, self.tr("Fichiers png (*.png);;Fichiers disk.png (*_disk.png);;Fichiers protus.png (*_protus.png);;Fichiers clahe.png (*_clahe.png);;Fichiers recon fits (*_recon.fits);;Fichiers fits (*.fits);;Tous les fichiers (*)"), self.pattern)
        self.pattern =file_list[1]
        if file_list[0] != [] :
            self.file_list_mosa=file_list[0]
            self.working_dir= self.get_dirpath(self.file_list_mosa[0])
            self.ui.mosa_dir_lbl.setText(self.working_dir)
            self.load_mosa_imagettes (self.file_list_mosa, "tab_mosa")
            file_names=[]
            for f in self.file_list_mosa :
                file_names.append (self.short_name(f))
            self.ui.mosa_image_view.ui.histogram.hide()
    
            self.ui.mosa_img_list_view.setFocus()
            self.ui.mosa_img_list_view.setCurrentRow(0)
    
    def load_mosa_imagettes(self, my_file_list, app_tab) :
        galx=100
        galy=100
        ext = self.check_extension (my_file_list)
        if ext != '' :
            try :
                page = self.ui.tab_main.findChild(QWidget, app_tab)
                if app_tab=='tab_mosa' :
                    self.ui.mosa_img_list_view.clear()
                self.ui.tab_main.setCurrentWidget(page)
                
                for file_name in my_file_list:
                    pro_item=QListWidgetItem()
                    iqm=self.img_variance(file_name)
                    # recupère data et transforme en Qpixmap suivant png, jpg ou fits
                    if ext=='png' or ext=='jpg':
                        
                        pix = QtGui.QPixmap(file_name)
                        self.pixmap = pix.scaled(galx, galy, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
                    if ext == 'fits' :
                        mydata, header= self.read_fits_image(file_name)
                        mydata = mydata.astype(np.int16)
                        h, w = mydata.shape
                        q_img = QtGui.QImage(np.ascontiguousarray(mydata), w, h, QtGui.QImage.Format_Grayscale16)
                        pix = QtGui.QPixmap.fromImage(q_img)
                        self.pixmap = pix.scaled(galx, galy, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation)
                        
                    pro_icon=QtGui.QIcon()
                    pro_icon.addPixmap(self.pixmap)
                    pro_item.setIcon(pro_icon)
                    #pro_item.setText(self.short_name(file_name)+' '+str(iqm))
                    if app_tab=="tab_mosa" :
                        self.ui.mosa_img_list_view.addItem(pro_item)    
                        pro_item.setText(self.short_name(file_name))
                    else :
                        pro_item.setText(self.short_name(file_name)+' '+str(iqm))
                    
            except:
                pass
    
    def mosa_img_list_view_sel_changed (self) :
        index=self.ui.mosa_img_list_view.currentRow()
        #print(self.short_name(self.file_list_mosa[index]))
        if index !=-1 :
            ext = self.get_extension (self.file_list_mosa[index])
            if ext == 'fits' :
                self.display_mosa_image_fits (self.file_list_mosa[index])
            if ext == 'png' or ext=='jpg' :
                self.display_mosa_image_png (self.file_list_mosa[index])
            self.ui.mosa_image_view.ui.histogram.show()
    
    def display_mosa_image_png(self, file_name) :
        image_data= cv2.imread(file_name,cv2.IMREAD_UNCHANGED)
        if len(image_data.shape) == 3 :
            image_data=cv2.cvtColor(image_data, cv2.COLOR_BGR2RGB)
        rotated_data = np.fliplr(np.rot90(image_data, 3))
        self.ui.mosa_image_view.setImage(rotated_data,autoRange=False, autoLevels=True)
        
    def display_mosa_image_fits(self, file_name) :
        image_data, header=self.read_fits_image(file_name)
        rotated_data = np.fliplr(np.rot90(image_data, 3))
        self.ui.mosa_image_view.setImage(rotated_data,autoRange=False, autoLevels=True)
        
    def run_mosa_clicked (self):
        ext = self.get_extension (self.file_list_mosa[0])
        myimg, iw, ih, centerX, centerY, solarR, x1, x2, y1, y2, flag_error= mo.prepare_files(self.working_dir, self.file_list_mosa)
        if flag_error == True :
            print(self.tr("Erreur lecture géométrie"))
        else :
            mosa_im, nbplan, nom_base = mo.create_mosa(self.working_dir, self.file_list_mosa, ext, myimg, iw, ih, centerX, centerY, solarR, x1, x2, y1, y2)
            mosa_im=np.array(mosa_im, dtype='uint16')
            rotated_data = np.fliplr(np.rot90(mosa_im, 3))
            self.ui.mosa_image_view.setImage(rotated_data,autoRange=False, autoLevels=True)
            # calcul image sharp
            if not self.ui.mosa_sharpnone_radio.isChecked():
                if self.ui.mosa_sharplow_radio.isChecked() :
                    self.sharp_level=1 
                else:
                    self.sharp_level=3 
                im_sharp=self.sharpenImage(mosa_im, self.sharp_level)
                ims=np.array(im_sharp, dtype="uint16")
                # sauve image sharp
                if nbplan ==1 :
                    file_corrected=self.working_dir+os.sep+nom_base+'_sharp.fits'
                    fits.writeto(file_corrected, ims, overwrite=True)
                rotated_data = np.fliplr(np.rot90(ims, 3))
                self.ui.mosa_image_view.setImage(rotated_data,autoRange=False, autoLevels=True)
                
                if nbplan== 3 :
                    # conversion BGR pour cv2 en RGB pour display
                    ims = cv2.cvtColor(ims, cv2.COLOR_BGR2RGB)
                    cv2.imwrite(self.working_dir+os.sep+ nom_base+'_sharp.png', ims)
                else:
                    cv2.imwrite(self.working_dir+os.sep+nom_base+'_sharp.png', ims)
            
    
        
    #--------------------------------------------------------------------------
    # tab anim
    #--------------------------------------------------------------------------
    
    def anim_img_list_open_clicked (self):
        anim_file_dialog=QFileDialog()
        self.ui.anim_stacked_widget.setCurrentIndex(0)
        file_list=[]
        self.ui.anim_image_view.clear()
        file_list = anim_file_dialog.getOpenFileNames(self, self.tr("Selectionner Images"), self.working_dir, self.tr("Fichiers png (*.png);;Fichiers disk png (*_disk.png);;Fichiers protus (*_protus.png);;Fichiers clahe png (*_clahe.png);;Fichiers free (*_free.png);;Tous les fichiers (*)"),self.pattern)
        self.pattern = file_list[1]
        if len(file_list[0]) != 0 :
            self.ui.anim_list.clear()
            self.file_list_anim=file_list[0]
            self.working_dir= self.get_dirpath(self.file_list_anim[0])
            self.ui.anim_dir_lbl.setText(self.working_dir)
            self.file_names=[]
            for f in self.file_list_anim :
                self.file_names.append (self.short_name(f))
            self.ui.anim_list.addItems (self.file_names)
            self.ui.anim_image_view.ui.histogram.hide()
            
            self.ui.anim_list.setCurrentRow(0)
            self.ui.anim_list.item(0).setSelected(True)
            self.current_index=0

    def anim_add_img (self):
        file_add_list=[]
        file_add_list = QFileDialog.getOpenFileNames(self, self.tr("Selectionner Images"), self.working_dir, self.tr("Fichiers png (*.png);;Fichiers disk png (*_disk.png);;Fichiers protus (*_protus.png);;Fichiers clahe (*_clahe.png);;Fichiers free (*_free.png);;Tous les fichiers (*)"), self.pattern)
        file_add_list=file_add_list[0]
        self.file_list_anim.extend (file_add_list)
        file_add_names=[]
        for f in file_add_list :
            file_add_names.append (self.short_name(f))
            self.file_names.append(self.short_name(f))
        self.ui.anim_list.addItems (file_add_names)


    def anim_open_sel_list (self):
        self.file_list_anim=[]
        file_name, _ = QFileDialog.getOpenFileName(self, self.tr("Ouvrir une liste de fichier"), self.working_dir, self.tr("Fichiers liste (t*_sel.txt)"))   
        # get directory out of file_name
        self.working_dir, _= os.path.split(file_name)
        #print(self.working_dir)
        if file_name :
            with open(file_name) as f:
                read_lines=f.readlines()
                n=[self.working_dir+os.sep+a.split("\n")[0] for a in read_lines]
                #print(n)
                if read_lines :
                    self.file_list_anim=n
                    
                    file_names=[]
                    for f in self.file_list_anim :
                        file_names.append (self.short_name(f))
                    self.ui.anim_list.addItems (file_names)                
                    self.ui.anim_list.setCurrentRow(0)
                    self.ui.anim_list.item(0).setSelected(True)
                    self.ui.anim_img_list_view.setFocus()
                    self.display_anim_image_png(file_name[0])
        
        
        
    def display_anim_image_png(self, file_name) :
        image_data= cv2.imread(file_name,cv2.IMREAD_UNCHANGED)
        rotated_data = np.fliplr(np.rot90(image_data, 3))
        self.ui.anim_image_view.setImage(rotated_data,autoRange=False, autoLevels=True)
        
    def anim_list_sel_changed (self) :
        index=self.ui.anim_list.currentRow()
        self.current_index=index
        #print(self.short_name(self.file_list_anim[index]))
        self.ui.anim_file_name_lbl.setText(self.short_name(self.file_list_anim[index]))
        self.ui.anim_stacked_widget.setCurrentIndex(0)
        if index !=-1 :
            self.display_anim_image_png (self.file_list_anim[index])
            
    def anim_next_clicked(self):
         index=self.current_index+1 
         if index < len(self.file_list_anim) :
             self.ui.anim_list.item(index).setSelected(True)
             self.display_anim_image_png(self.file_list_anim[index])
             self.current_index=index
             self.ui.anim_file_name_lbl.setText(self.short_name(self.file_list_anim[index]))
             
             
    def anim_prev_clicked(self):
         index=self.current_index-1 
         if index >=0 :
             self.ui.anim_list.item(index).setSelected(True)
             self.display_anim_image_png(self.file_list_anim[index])
             self.current_index=index
             self.ui.anim_file_name_lbl.setText(self.short_name(self.file_list_anim[index]))       
             
    def anim_remove_clicked(self):
         #index=self.ui.anim_list.currentRow()
         index=self.current_index
         self.ui.anim_list.item(index).setSelected(True)
         self.ui.anim_list.takeItem(index)
         del self.file_list_anim[index]
         del self.file_names[index]
         self.ui.anim_image_view.clear()
         #
         new_index=index
         if new_index>len(self.file_list_anim)-1 :
             new_index=len(self.file_list_anim)-1
         self.ui.anim_list.item(new_index).setSelected(True)
         self.current_index=new_index
         self.ui.anim_file_name_lbl.setText(self.short_name(self.file_list_anim[new_index]))       



    def anim_flip_hb (self) :
        img=self.ui.anim_image_view.image
        flip_img= cv2.flip(img,1)
        self.ui.anim_image_view.setImage(flip_img)
        rot_data = np.fliplr(np.rot90(flip_img, 3))
        cv2.imwrite(self.file_list_anim[self.current_index], rot_data)
        #print(self.select_files[self.current_index]+' saved')
        
    def anim_flip_dg (self) :
        img=self.ui.anim_image_view.image
        flip_img= cv2.flip(img,0)
        self.ui.anim_image_view.setImage(flip_img)
        rot_data = np.fliplr(np.rot90(flip_img, 3))
        cv2.imwrite(self.file_list_anim[self.current_index], rot_data)
        #print(self.select_files[self.current_index]+' saved')
        
    def anim_roi(self) :
        if self.myROI :
            if self.myROI.scene() is  self.ui.anim_image_view.getView().scene() :
                self.ui.anim_image_view.removeItem(self.myROI)
                self.myROI=[]
        else :
            iw= self.ui.anim_image_view.image.shape[0]//2
            ih=self.ui.anim_image_view.image.shape[1]//2
            self.myROI=pg.RectROI((ih-50,iw-50), (100,100), centered=False, sideScalers=True)
            self.ui.anim_image_view.addItem(self.myROI)
            
    def anim_crop (self) :  # aka prepare animation
        if self.myROI :
            # ROI pos x,y
            x1=int(self.myROI.pos()[0])+1
            y1=int(self.myROI.pos()[1])+1
            dx=int(self.myROI.size()[0])
            dy=int(self.myROI.size()[1])
            #
            self.crop_file_list=[]
            self.crop_file_names=[]
            self.file_list_bak=[]
            self.file_list_bak=self.file_list_anim
            self.file_names_bak=self.file_names
            for f in self.file_list_anim :
                #myimg= cv2.imread(f,cv2.IMREAD_UNCHANGED)
                myimg=Image.open(f)
                myimg=np.asarray(myimg)
                crop_img=myimg[y1:y1+dy,x1:x1+dx]
                #cv2.imwrite(self.working_dir+os.sep+'cr'+self.short_name(f), crop_img)
                Image.fromarray(crop_img).convert("I").save(self.working_dir+os.sep+'cr'+self.short_name(f)) 
                self.crop_file_list.append(self.working_dir+os.sep+'cr'+self.short_name(f))
                self.crop_file_names.append('cr'+self.short_name(f))
                #print('cr'+self.short_name(f))
            #
            self.ui.anim_list.clear()
            self.ui.anim_list.addItems (self.crop_file_names)
            self.file_list_anim=self.crop_file_list
            self.ui.anim_list.setCurrentRow(0)
            self.anim_roi()
            self.ui.anim_image_view.autoRange()
        else :
            # pas de ROI on prend les images en entier
            self.file_list_bak=self.file_list_anim
            self.file_names_bak=self.file_names
        
        # met a jour les infos pour l'animation
        self.anim_time_sample_validate()
    
    def anim_reset(self) :
        self.file_list_anim=self.file_list_bak
        self.ui.anim_list.clear()
        self.ui.anim_stacked_widget.setCurrentIndex(0)
        self.ui.anim_list.addItems(self.file_names_bak)
        self.ui.anim_list.setCurrentRow(0)
        self.ui.anim_image_view.autoRange()
        
    def anim_time_sample_validate(self) :
        self.ui.anim_stacked_widget.setCurrentIndex(0)
        img= cv2.imread(self.file_list_anim[0],cv2.IMREAD_UNCHANGED)
        h=img.shape[0]
        w=img.shape[1]
        self.ui.anim_ih_lbl.setText(str(h))
        self.ui.anim_iw_lbl.setText(str(w))
        self.flag_nologtxt=False
        nb_img_acquise = len(self.file_list_anim)
        self.ui.anim_nb_acquise_lbl.setText(str(nb_img_acquise))
        if self.ui.anim_nb_total_text.text().isnumeric() :
            nb_trame_totale=int(self.ui.anim_nb_total_text.text())
        else :
            print(self.tr("Nb final d'image : doit etre valeur entiere numérique"))
            self.ui.anim_nb_total_text.setText(str(10))
            nb_trame_totale=int(self.ui.anim_nb_total_text.text())
        
        if self.ui.anim_interp_checkbox.isChecked() :
            # recupere heure dans chaque fichier _log.txt
            # si fichier clahe alors on remonte repertoire d'un cran
            if self.file_list_bak[0].find("_clahe.") != -1 :
                log_dir = os.path.dirname(self.working_dir)
            else :
                log_dir = self.working_dir
            try :                    
                files_log = [os.path.basename(get_baseline(os.path.splitext(x)[0])+"_log.txt") for x in self.file_list_bak]
                #jd,_=[get_time_from_log(log_dir+os.sep+x) for x in files_log]
                result = [get_time_from_log(log_dir+os.sep+x) for x in files_log]
                jd = [t[0] for t in result]
                jd=[int(j) for j in jd]
                time_seq=np.argsort(jd)
                if np.all(time_seq==0) :
                    raise Exception
                # on recre une sequence de t et de nom de fichier ordonnné
                new_t=[jd[x] for x in time_seq]
                self.file_list_anim=[self.file_list_anim[j] for j in time_seq]
                #print(t, time_seq, new_t, self.file_list_anim)
                self.d_sec=[x-new_t[0] for x in new_t]
                #print(self.d_sec)
                #s_d_sec=[str(d) for d in d_sec]
                if new_t[0]==new_t[1]:
                    print(self.tr('erreur de datation'), jd)
                else:
                    #time_stamp=', '.join(s_d_sec)
                    self.duration= self.d_sec[-1]
            except :
                self.flag_nologtxt=True
                print (self.tr("Pas de fichier _log.txt"))
                self.ui.anim_interp_checkbox.setChecked(False)
                self.d_sec=np.arange(0,(10*nb_img_acquise), 10)
        
        else :
            self.d_sec=np.arange(0,(10*nb_img_acquise), 10)
            
        self.duration= self.d_sec[-1]
        nb_trame_totale=int(self.ui.anim_nb_total_text.text())
        self.echt=round(self.duration/nb_trame_totale)
        
        if self.ui.anim_fps_text.text().isnumeric() :
            self.frps=int(self.ui.anim_fps_text.text())
            if self.frps > 30 :
                print(self.tr("Images par seconde supérieure à 30 i/s"))
                self.ui.anim_fps_text.setText(str(30))
                self.frps=int(self.ui.anim_fps_text.text())
        else :
            print(self.tr("Images par seconde : doit etre valeur entiere numérique"))
            self.ui.anim_fps_text.setText(str(1))
            self.frps=int(self.ui.anim_fps_text.text())
            
        duree_film = nb_trame_totale // self.frps
        self.ui.anim_duree_film_lbl.setText(str(duree_film))
        
        # check si temps de calcul trop long
        wi=int(self.ui.anim_iw_lbl.text())
        he=int(self.ui.anim_ih_lbl.text())
        nbi= int(self.ui.anim_nb_total_text.text())
        self.flag_stop = False
        if wi >=2000 or he >=2000 or nbi >= 500:
            msg= self.tr("Grande dimension d'image : le temps de calcul peut être très long - voulez-vous continuer ?")
            myquestion = QMessageBox.question(self, 'Information', msg, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if myquestion == QMessageBox.Yes:
                self.flag_stop = False
            else:
                self.flag_stop = True
            

    
    def anim_interp(self) :
        if self.flag_nologtxt == False :
            self.anim_time_sample_validate()

    
    def anim_create(self):
        self.anim_time_sample_validate()
        if self.flag_stop == False : 
            nb_trame_totale=int(self.ui.anim_nb_total_text.text())
            nb_img_acquise = len(self.file_list_anim)
            try :
                reduction= float(self.ui.anim_reduc_text.text())
            except :
                print(self.tr("facteur d'échelle : doit être une valeur numérique"))
                reduction = 1
                self.ui.anim_reduc_text.setText(str(reduction))
            
            basefich= self.ui.anim_name_text.text()
            # interpolation temporelle
            # echt est l'echantillonage temporel
            # d_sec est la liste des valeurs de temps des images acquises
            # si pas de datation avec _lot.txt on fixe intervalle fixe de 10
            img=Image.open(self.file_list_anim[0])
            im1=np.array(img)
            #print(im1.shape)
            print(str(len(self.file_list_anim))+ self.tr(' fichiers'))
            h,w=im1.shape
            vol_im=np.zeros((len(self.file_list_anim),h,w)) # volume des images acquises
            vol_med=[]
            for k in range(0,len(self.file_list_anim)):
                fname=self.file_list_anim[k]
                #img=cv2.imread(fname,cv2.IMREAD_UNCHANGED)
                img=Image.open(fname)
                im=np.array(img)
                vol_im[k,:,:]=im             
            
            x=self.d_sec
            
            step=self.echt
            print("Datations : ",self.d_sec)
            #end_t= round(self.d_sec[len(self.file_list_anim)-1]/step)*step
            end_t=self.duration
            xi=np.arange(0,end_t,step)
            #print (len(xi), xi)
            v=np.zeros((len(xi),h,w)) #volume des images interpolées
            print (str(len(xi))+self.tr(' trames'))
            self.ui.anim_progress_bar.setMaximum(h-1)
            self.ui.anim_progress_bar.setVisible(True)
            if nb_trame_totale != nb_img_acquise :
                # on interpole
                for li in range(0,h):
                    self.ui.anim_progress_bar.setValue(li)
                    #print("\r"+'li: '+str(li)+"/"+str(h-1),end="")
                    #sys.stdout.flush()
                    for co in range(0,w):
                        lg=vol_im[:,li,co]
                        #print(lg)
                        f=interp1d(x,lg)
                        li_interpolated=np.empty((len(xi)))
                        li_interpolated=f(xi)
                        #print(li_interpolated)
                        v[:,li,co]=li_interpolated
                
            else :
                v = vol_im
                    
            a=np.empty((h,w))
            frame=[]
            self.ui.anim_progress_bar.setVisible(False)
            if self.myROI :
                # ROI pos x,y
                x1=int(self.myROI.pos()[0])+1
                y1=int(self.myROI.pos()[1])+1
                dx=int(self.myROI.size()[0])
                dy=int(self.myROI.size()[1])
                flag_unif = True
                # on reset la ROI
                self.anim_roi()
                print(self.tr("ROI : uniformisation des intensités"))
            else :
                # no uniformisation
                flag_unif = False
            
            
            if flag_unif :
                for k in range(0,len(xi)):
                    a=np.array(v[k])
                    # calcul intensité moy au centre de l'image sur zone de de +/- 100 pixels
                    moy=np.median(a[y1:y1+dy, x1:x1+dx])
                    vol_med.append(moy)
                
                # uniformisation intensité
                vol_max = np.max(vol_med)
                
            
            
            #sauve les trames uniformisées en intensité en png 
            # sauvegarde des images unitaires dans un repertoire stack 
            self.anim_dir = self.working_dir+os.sep+'Animation'
            if not os.path.isdir(self.anim_dir):
               os.makedirs(self.anim_dir)
               
            for k in range(0,len(xi)):
                #a=np.array(v[k], dtype='uint16')
                a=np.array(v[k])
                if flag_unif :
                    ratio = vol_max / vol_med[k]
                else :
                    ratio = 1
                
                a=a*ratio
                Image.fromarray(a).convert("I").save(self.anim_dir+os.sep+'fr'+str(k)+'.png')
                frame.append('fr'+str(k)+'.png')
              
            try :
                    # genere un gif animated
                    self.gif_images=[]
                    # genere un fichier video
                    print("create video")
                    self.anim_file_name=self.working_dir+os.sep+basefich+'.mp4' 
                    self.anim_file_name_gif=self.working_dir+os.sep+basefich+'.gif' 
                    #filename=basefich+'.avi'  python conversion float en int
                    #img=Image.open(frame[0])
                    #h=img.height
                    #w=img.width
                    height, width=(int(h*reduction),int(w*reduction))
                    img=[]
                    #image_files=[]
    
                    #print(height, width)
                    
                    fourcc = cv2.VideoWriter_fourcc(*'avc1')
                    #fourcc = cv2.VideoWriter_fourcc(*"mp4v")

                    out = cv2.VideoWriter(self.anim_file_name, fourcc,self.frps, (width, height),0)
                    #out = cv2.VideoWriter(filename, fourcc,frps, (width, height),1)
                    
                    for k in range(0,len(frame) ):
                        
                        fname=frame[k]
                        img=cv2.imread(self.anim_dir+os.sep+fname)
                        img2=cv2.resize(img,(width, height),interpolation = cv2.INTER_AREA)
                        self.gif_images.append(Image.fromarray(img2))
                        out.write(img2)
                        
                        
            
                    out.release()
                    print("Animation : ",self.anim_file_name)
                    im=self.gif_images[0]
                    im.save(self.anim_file_name_gif, save_all=True, append_images=self.gif_images[1:], duration=int(1/self.frps)*1000, loop=0)
                    self.ui.anim_stacked_widget.setCurrentIndex(1)
                    self.mediaPlayer=QMediaPlayer(self)
                    self.mediaPlayer.setVideoOutput(self.anim_video_player)
                    self.mediaPlayer.setSource(QUrl.fromLocalFile(self.anim_file_name))
                    self.mediaPlayer.play()
            except :
                if out.isOpened() :
                    out.release()
                
    def anim_play(self) :

        #filename='C:\\Users\\valer\\Desktop\\SharpCap Captures\\2024-04-13\\Capture_demo\\inti_mp4.mp4'
        self.mediaPlayer=QMediaPlayer(self)
        self.mediaPlayer.setVideoOutput(self.anim_video_player)
        self.mediaPlayer.setSource(QUrl.fromLocalFile(self.anim_file_name))
        self.mediaPlayer.setLoops(1)
        self.mediaPlayer.play()

    # tab map
    #--------------------------------------------------------------------------
    
    def map_reset(self):
        self.ui.map_image_ref_view.view.setRange(xRange=[200,self.map_iw], yRange=[0,1500], padding=0)
        #self.ui.map_image_ref_view.setImage(rotated_data,autoRange=False, autoLevels=True)
        
    def map_goto (self):
        # None, caH&K, hBeta, Mg Triplet, Fe XIV 5303, HeliumD3 & Na D, Fe I 6173 - 6302, Fe X 6375, H-alpha]
        line_pos=[0,200,6500,8500,9300,13300,16000, 17000,18500]
        index=self.ui.map_goto_combo.currentIndex()
        self.ui.map_image_ref_view.view.setRange(xRange=[200,self.map_iw], yRange=[line_pos[index],line_pos[index]+1500], padding=0)
        
    def map_image_open (self) :
        self.file_map =''
       
        file_map = QFileDialog.getOpenFileName(self, "Selectionner Image", self.working_dir, "Fichiers png (*.png);;Tous les fichiers (*)")
        self.file_map=file_map[0]
        self.working_dir= self.get_dirpath(self.file_map)
        self.ui.map_file_name_lbl.setText(self.file_map)
        
        
        pix = QtGui.QPixmap(self.file_map)
        s=self.ui.map_img_to_find_lbl.size()
        pixmap = pix.scaled(s.width(),s.height(), Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)  
        self.ui.map_img_to_find_lbl.setPixmap(pixmap)
        self.ui.map_img_to_find_lbl.setScaledContents(True)
        
    def map_localize(self) :
        my_pixel_size= float(self.ui.map_pixel_size_text.text())
        pixel_ref=4.8  # la taille de pixel de l'image spectre.png de reference
        ratio_pix= my_pixel_size/pixel_ref
        
        img_r=cv2.imread(resource_path('sun_spectre.png'), cv2.IMREAD_GRAYSCALE)
        ih,iw = img_r.shape[0], img_r.shape[1]
        
        template=cv2.imread(self.file_map, cv2.IMREAD_GRAYSCALE)
        if self.ui.map_flipud_checkbox.isChecked() :
            template=np.flipud(template)
        temp_r= synth_spectrum(template, ratio_pix)
        zih,ziw = temp_r.shape[0], temp_r.shape[1]

        maxLoc = template_locate (img_r, temp_r)
        (startX, startY) = maxLoc
        starty1=startY-100
        self.ui.map_image_ref_view.view.setRange(xRange=[200,self.map_iw], yRange=[starty1,starty1+1500], padding=0)
        
        # zone spectre anotation
        line=QGraphicsLineItem(200,startY,self.map_iw,startY)
        line.setPen(pg.mkPen(color=(200, 0, 0), width=4))
        line.setZValue(1000)
        self.ui.map_image_ref_view.view.addItem(line)  
        line=QGraphicsLineItem(200,startY+zih,self.map_iw,startY+zih)
        line.setPen(pg.mkPen(color=(200, 0, 0), width=4))
        line.setZValue(1000)
        self.ui.map_image_ref_view.view.addItem(line)  
        
        # zone spectre couleur
        ratio=self.map_color_iw/self.map_ih
        try :
            if self.lineA.scene() is  self.ui.map_image_color_view.getView().scene() :
                self.ui.map_image_color_view.removeItem(self.lineA)
                self.ui.map_image_color_view.removeItem(self.lineB)
        except :
            pass
        self.lineA=QGraphicsLineItem(startY*ratio, 0,startY*ratio, self.map_color_ih)
        self.lineA.setPen(pg.mkPen(color=(255, 255, 255), width=4))
        self.lineA.setZValue(1000)
        self.ui.map_image_color_view.view.addItem(self.lineA)  
        self.lineB=QGraphicsLineItem((startY+zih)*ratio,0,(startY+zih)*ratio, self.map_color_ih)
        self.lineB.setPen(pg.mkPen(color=(255, 255, 255), width=4))
        self.lineB.setZValue(1000)
        self.ui.map_image_color_view.view.addItem(self.lineB) 
        
        zone_crop=img_r[startY:startY+zih,:]
        # display zone trouvée
        q_img = QtGui.QImage(zone_crop, zone_crop.shape[1], zone_crop.shape[0],QtGui.QImage.Format.Format_Grayscale8)
        pix = QtGui.QPixmap.fromImage(q_img)
        s=self.ui.map_img_found_lbl.size()
        pixmap = pix.scaled(s.width(),s.height(),Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation)  
        self.ui.map_img_found_lbl.setPixmap(pixmap)
        self.ui.map_img_found_lbl.setScaledContents(True)
        
    # tab magnet
    #-------------------------------------------------------------------------
    
    def mag_droite_open (self) :
        self.polar ='droite'
        self.mag_open()
    
    def mag_gauche_open (self) :
        self.polar='gauche'
        self.mag_open()
    
    def mag_open (self) :

        file_polar = QFileDialog.getOpenFileNames(self, "Selectionner fichier polarisation", self.working_dir, "Fichiers fits (*.fits)")
        file_polar=file_polar[0]
        self.working_dir= self.get_dirpath(file_polar[0])
        if self.polar== 'droite' :
            self.file_polar_droite=[]
            self.ui.mag_droite_list.clear()
            for f in file_polar :
                self.file_polar_droite.append(self.short_name(f))
            self.ui.mag_droite_list.addItems(self.file_polar_droite)
            
        if self.polar == 'gauche' :
            self.file_polar_gauche=[]
            self.ui.mag_gauche_list.clear()
            for f in file_polar :
                self.file_polar_gauche.append(self.short_name(f))
            self.ui.mag_gauche_list.addItems(self.file_polar_gauche)
            
    
    def mag_go(self) :
        flag_ok =True
        # tri polarisation droite r- et b-
        pos_r=self.file_polar_droite[0].find('r-')
        pos_b=self.file_polar_droite[0].find('b-')
        if pos_r != - 1 :
            self.racine_droite= self.file_polar_droite[0].split('r-')[0]
        if pos_b != -1 :
            self.racine_droite= self.file_polar_droite[0].split('b-')[0]
       
        
        # test si tous les noms de fichiers de la liste commencent par la meme racine
        # test si il manque des polar r ou b
        check_racine=sum(self.racine_droite in f for f in self.file_polar_droite)
        if check_racine != len(self.file_polar_droite) :
            print(self.tr("Polarisation droite : Erreur noms de fichier"))
            self.racine_droite=''
            flag_ok=False
        
            
        if self.racine_droite != '' :
            nb_filtre_droite_r = sum(self.racine_droite+'r-' in f for f in self.file_polar_droite)
            nb_filtre_droite_b = sum(self.racine_droite+'b-' in f for f in self.file_polar_droite)
            if nb_filtre_droite_r != nb_filtre_droite_b or nb_filtre_droite_r==0 or nb_filtre_droite_b==0:
                print(self.tr("Polarisation droite : Erreur nombre de fichiers polarisation droite r et b différents"))
                flag_ok=False
                
            # tri polarisation gauche r- et b-
            pos_r=self.file_polar_gauche[0].find('r-')
            pos_b=self.file_polar_gauche[0].find('b-')
            if pos_r != - 1 :
                self.racine_gauche= self.file_polar_gauche[0].split('r-')[0]
            if pos_b != -1 :
                self.racine_gauche= self.file_polar_gauche[0].split('b-')[0]
           
            
            # test si tous les noms de fichiers de la liste commencent par la meme racine
            # test si il manque des polar r ou b
            check_racine=sum(self.racine_gauche in f for f in self.file_polar_gauche)
            if check_racine != len(self.file_polar_gauche) :
                print(self.tr("Polarisation gauche : Erreur noms de fichier"))
                self.racine_gauche=''
                flag_ok=False
            
            if self.racine_gauche != '' :
                nb_filtre_gauche_r = sum(self.racine_gauche+'r-' in f for f in self.file_polar_gauche)
                nb_filtre_gauche_b = sum(self.racine_gauche+'b-' in f for f in self.file_polar_gauche)
                
                if nb_filtre_gauche_r != nb_filtre_gauche_b or nb_filtre_gauche_r==0 or nb_filtre_gauche_b==0:
                    print(self.tr("Polarisation gauche : Erreur nombre de fichiers polarisation gauche r et b différents"))
                    flag_ok=False

            if flag_ok : 
                
                img_mag, img_mag0, img_cont, polb1, polb2, polr1, polr2, hdr= magnet.magnetogramme (self.working_dir+os.sep,self.racine_droite, self.racine_gauche, nb_filtre_droite_b,nb_filtre_gauche_b)
                                    
                rotated_data = np.fliplr(np.rot90(img_mag0, 3))
                self.ui.mag_img_view.setImage(rotated_data,autoRange=False, autoLevels=True)
                
                # sauve les images en fits et png mag_s, mag_s0, et cont et les images de polarisation intermediaires et les ajoutes à la liste
                self.ui.mag_results_list.clear()
                self.file_results=[]
                f_fits=[]
                f_png=[]
                img_fits=[]
                img_fits = [img_mag,img_cont, polb1,polb2, polr1, polr2]
                img_png= [img_mag+32767, img_cont]
                
                
                if self.ui.mag_corrige_chk.isChecked() :
                    im= np.copy(img_png[0])
                    img_png[0]=self.mag_corrige_bandes(im)
                    
                f_fits.append(self.working_dir+os.sep+ "mag_s.fits")
                f_png.append(self.working_dir+os.sep+ "mag_s.png")
                f_fits.append(self.working_dir+os.sep+ "mag_cont.fits")
                f_png.append (self.working_dir+os.sep+ "mag_cont.png")
                
                f_fits.append(self.working_dir+os.sep+ "tmp_b+45.fits")
                f_fits.append(self.working_dir+os.sep+ "tmp_r+45.fits")
                f_fits.append(self.working_dir+os.sep+ "tmp_b-45.fits")
                f_fits.append(self.working_dir+os.sep+ "tmp_r-45.fits")
                
                for i in range (0, len(f_fits)) :
                    self.save_fits_image(f_fits[i], img_fits[i], hdr, nb_bytes=32)
                    
                for i in range (0, len(f_png)) :
                    self.save_png_image(f_png[i], img_png[i])
                    self.ui.mag_results_list.addItem(self.short_name(f_png[i]))
                    self.file_results.append(f_png[i])
                self.ui.mag_results_list.setCurrentRow(0)
                
    
    def mag_corrige_bandes (self, img) : 
        seuil,mask = pic_histo(img)
        img=np.rot90(img,1)
        belle_image, chull, neg_chull, BelleImage = helium_flat(img, seuil, mask)
        belle_image=np.rot90(belle_image,3)
                
        return belle_image
    
    
    def mag_results_list_sel_changed (self) :
        index = self.ui.mag_results_list.currentRow()
        if index !=-1 :
            img_data = cv2.imread(self.file_results[index], cv2.IMREAD_ANYDEPTH)
            rotated_data = np.fliplr(np.rot90(img_data, 3))
            self.ui.mag_img_view.setImage(rotated_data,autoRange=False, autoLevels=True)
            
            
    def mag_gauche_list_sel_changed (self) :
        index = self.ui.mag_gauche_list.currentRow()
        if index !=-1 :
            self.mag_display_fits (self.working_dir+os.sep+self.file_polar_gauche[index])
        
    
    def mag_droite_list_sel_changed (self) :
        index = self.ui.mag_droite_list.currentRow()
        if index !=-1 :
            self.mag_display_fits (self.working_dir+os.sep+self.file_polar_droite[index])
            
    def mag_display_fits (self, file_name) :
        image_data, header = self.read_fits_image(file_name)
        rotated_data = np.fliplr(np.rot90(image_data, 3))
        self.ui.mag_img_view.setImage(rotated_data,autoRange=False, autoLevels=True)
            
    
    # tab ser
    #-------------------------------------------------------------------------
    
    def ser_open (self) :
        self.file_ser =''
       
        file_ser = QFileDialog.getOpenFileName(self, "Selectionner fichier SER", self.working_dir, "Fichiers SER (*.SER)")
        self.file_ser=file_ser[0]
        self.ser_read()
        
    def ser_read(self) :
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.working_dir= self.get_dirpath(self.file_ser)
        self.ui.ser_filename_lbl.setText(self.file_ser)
        
        try:
            scan = Serfile(self.file_ser, False)
        
            self.FrameCount = scan.getLength()    #      return number of frame in SER file.
            Width = int(scan.getWidth())          #      return width of a frame
            Height = int(scan.getHeight())        #      return height of a frame
            self.ser_hdr = scan.getHeader()
            
            # forme le volume de data 
            # initialize le tableau qui recevra l'image somme de toutes les trames
            # garde une copie des trames originales si on veut trimmer le fichier
            FrameIndex=0
            ser_volume=np.zeros((self.FrameCount,Width, Height),dtype='uint16')
            self.ser_raw=np.zeros((self.FrameCount,Height, Width),dtype='uint16')
            
            while FrameIndex < self.FrameCount:
                try :
                    num_raw = scan.readFrameAtPos(FrameIndex)
                    num=np.flipud(np.rot90(num_raw))
                except:
                    print(FrameIndex)
    
                # ajoute la trame au volume
                ser_volume[FrameIndex]=num
                self.ser_raw[FrameIndex]=num_raw
                #increment la trame et l'offset pour lire trame suivant du fichier .ser
                FrameIndex=FrameIndex+1
            
            self.ui.ser_view.setImage(ser_volume)
            mid_pos= self.ui.ser_view.image.shape[1]//2
            self.ui.ser_trame_start_text.setText(str(1))
            self.ui.ser_trame_end_text.setText(str(self.FrameCount))
            self.ui.ser_view.view.addItem(self.v_bar_pro)
            self.v_bar_pro.setPos(mid_pos) # position curseur vertical
            
            
            # Cherche fichier sunscan raw (attention appli mobile sunscan ne donne pas une image raw de la bonne dimension)
            # ou le cherche dans sous repertoire compléments ou repertoire de travail
            basefich= '_'+self.short_name(self.file_ser)[:-4]
            self.flag_raw=True
            
            if basefich.find('_scan') != -1 : 
                basefich= basefich.replace('_scan', "sunscan")[1:]
            
            file_raw=self.working_dir+os.sep+'Complements'+os.sep+basefich+'_raw.png'
            if file_exist(file_raw) :
                img_raw=cv2.imread(file_raw,cv2.IMREAD_UNCHANGED)
                img_raw = np.fliplr(np.rot90(img_raw, 3))
                # affiche fichier raw
                self.ui.ser_raw_view.setImage(img_raw)
                self.ui.ser_raw_filename_lbl.setText(file_raw)
            else :
                file_raw=self.working_dir+os.sep+os.sep+basefich+'_raw.png'
                if file_exist(file_raw) :
                    img_raw=cv2.imread(file_raw,cv2.IMREAD_UNCHANGED)
                    img_raw = np.fliplr(np.rot90(img_raw, 3))
                    # affiche fichier raw
                    self.ui.ser_raw_view.setImage(img_raw)
                    self.ui.ser_raw_filename_lbl.setText(file_raw)
                else :
                    print(self.tr('Fichier non trouvé : ')+file_raw)
                    self.flag_raw=False
            self.ui.ser_view.setCurrentIndex(self.FrameCount//4)
        except:
            print(self.tr('Erreur ouverture fichier : ')+self.file_ser)
        
        QApplication.restoreOverrideCursor()
        
    def ser_saveas (self) :

        pos=self.file_ser.rfind('.')
        nom_suggere =self.working_dir+os.sep+self.file_ser[:pos]
        
        file_name,_=QFileDialog.getSaveFileName(self, self.tr("Sauver Trame png"), nom_suggere, self.tr("Fichiers png (*.png);;Tous les fichiers (*)"))
        
        if file_name :
            index = self.ui.ser_view.currentIndex
            myimage=self.ui.ser_view.image[index]
            
            myimage=np.flipud(np.rot90(myimage))

            # ajustment des seuils
            levels = self.ui.ser_view.getLevels()
            sbas,shaut = levels
            if shaut != sbas :
                myimage = np.clip((myimage-sbas)/(shaut-sbas)*65535,0,65535).astype(np.uint16)
            
            cv2.imwrite(file_name, myimage)
        
    def ser_trim_save (self) :
        if self.ui.ser_trame_start_text.text().isnumeric() :
            trame_deb= int(self.ui.ser_trame_start_text.text())
        else :
            print(self.tr("Valeur trame début doit etre entière et numérique"))
        
        if self.ui.ser_trame_end_text.text().isnumeric() :
            trame_fin= int(self.ui.ser_trame_end_text.text())
        else :
            print(self.tr("Valeur trame fin doit etre entière et numérique"))
        
        if trame_fin > self.FrameCount :
            trame_fin=self.FrameCount
            self.ui.ser_trame_end_text.setText(str(trame_fin))
        if trame_deb <=0 :
            trame_deb=1
            self.ui.ser_trame_start_text.setText(str(trame_deb))
        
        # test crop ser
        filename_trim,_=QFileDialog.getSaveFileName(self, self.tr("Sauver fichier ser"), self.working_dir, self.tr("Fichiers ser (*.ser)"))
        if filename_trim :
            scan_crop = Serfile(self.working_dir+os.sep+'ser_crop.ser', True, self.ser_hdr)
            scan_crop.createNewHeader(self.ser_hdr)
            f=self.ser_raw[trame_deb:trame_fin+1,:,:]
            scan_crop.addFrames(f)        
            fr=scan_crop.getLength()
            print("write ser trim : ", fr)
            print(filename_trim)

            
        
    
    def ser_frame_changed (self) :

        self.ui.ser_frame_nb_lbl.setText(str(self.ui.ser_view.currentIndex))
        
        if self.flag_raw :
            self.ui.ser_raw_view.view.addItem(self.v_bar)
            self.v_bar.setPos(int(self.ui.ser_view.currentIndex)) # position curseur vertical
            
        self.ser_view_profil(int(self.v_bar_pro.value()))
    
    def ser_goto_frame (self) :
        goto_frame=int(self.ui.ser_goto_frame_text.text())
        self.ui.ser_view.setCurrentIndex(goto_frame)
        
    def ser_play (self) :
        self.ui.ser_view.play(50)
    
    def ser_stop (self) :
        self.ui.ser_view.play(0)
        
    
    def ser_trame_cursor_sig_dragged(self) :
        pos= int(self.v_bar_pro.value())
        self.ser_view_profil(pos)
        try :
            if self.mypoint.scene() is self.ui.ser_raw_view.getView().scene():
                self.ui.ser_raw_view.view.removeItem(self.mypoint)
            if self.flag_raw :
                # point rouge
                self.mypoint=QGraphicsEllipseItem(0,0,6,6)
                self.mypoint.setPen(pg.mkPen(color=(250, 120, 0), width=12))
                self.mypoint.setPos(self.ui.ser_view.currentIndex-3, pos-3)
                self.ui.ser_raw_view.view.addItem(self.mypoint)  
        except :
            pass
        
        
    
    def ser_raw_cursor_sig_dragged(self):
        if self.flag_raw :
            self.v_bar.label.setFormat("{:0.0f}".format(self.v_bar.value()))
            self.ui.ser_view.setCurrentIndex(int(self.v_bar.value()))
            try :
                if self.mypoint.scene() is self.ui.ser_raw_view.getView().scene():
                    self.ui.ser_raw_view.view.removeItem(self.mypoint)
            except :
                pass
            
    def ser_view_profil(self, x) :
        
        try :
            # recupere le profil spectral 
            trame_index=self.ui.ser_view.currentIndex
            spectre_img=self.ui.ser_view.image
            my_trame = spectre_img[trame_index]
            ih = spectre_img[trame_index].shape[1]
            iw = spectre_img[trame_index].shape[0]
            
            # test si dans image
            if x >=0 and x<= iw :
                
                lamb=np.arange (0,ih)
                profil=my_trame[x:x+1,:][0]
                self.ser_posx = x
                
                # affiche profile
                self.ui.spectre_view.clear()
                self.ui.spectre_view.setBackground('w')
                pen=pg.mkPen(color='blue',width=1.5)
                profile_name= 'Trame '+ str(trame_index)
                self.myplot = self.ui.spectre_view.plot(lamb, profil, pen=pen, name=profile_name, maxTickLength=-100)
        except :
            print(trame_index,x, ih, iw)

    def ser_posx_prev (self) :
        x=self.ser_posx - 1
        # recupere le profil spectral 
        trame_index=self.ui.ser_view.currentIndex
        spectre_img=self.ui.ser_view.image
        my_trame = spectre_img[trame_index]
        ih = spectre_img[trame_index].shape[1]
        lamb=np.arange (0,ih)
        if x>=0 :
            # point rouge
            try : 
                #if self.mypoint.scene() is  self.ui.ser_view.getView().scene() :
                self.ui.ser_raw_view.removeItem(self.mypoint)
            except :
                pass
            if self.flag_raw :
                self.mypoint=QGraphicsEllipseItem(0,0,6,6)
                self.mypoint.setPen(pg.mkPen(color=(250, 120, 0), width=12))
                self.mypoint.setPos(self.ui.ser_view.currentIndex-3, x-3)
                self.ui.ser_raw_view.view.addItem(self.mypoint)  
            
            profil=my_trame[x:x+1,:][0]
            self.ser_posx = x
            self.ui.ser_posx_lbl.setText(str(x))
            # affiche profile
            self.ui.spectre_view.clear()
            self.ui.spectre_view.setBackground('w')
            pen=pg.mkPen(color='blue',width=1.5)
            profile_name= 'Trame '+ str(trame_index)
            self.myplot = self.ui.spectre_view.plot(lamb, profil, pen=pen, name=profile_name, maxTickLength=-100, autoLevels=False)
            
            # affiche ligne verticale sur le fichier ser
            self.v_bar_pro.setPos(x)

    
    def ser_posx_next(self) :
        x=self.ser_posx + 1
        # recupere le profil spectral 
        trame_index=self.ui.ser_view.currentIndex
        spectre_img=self.ui.ser_view.image
        my_trame = spectre_img[trame_index]
        ih = spectre_img[trame_index].shape[1]
        iw=spectre_img[trame_index].shape[0]
        lamb=np.arange (0,ih)
        if x<=iw :
            # point rouge
            try : 
                #if self.mypoint.scene() is  self.ui.ser_view.getView().scene() :
                self.ui.ser_raw_view.removeItem(self.mypoint)
            except :
                pass
            if self.flag_raw :
                self.mypoint=QGraphicsEllipseItem(0,0,6,6)
                self.mypoint.setPen(pg.mkPen(color=(250, 120, 0), width=12))
                self.mypoint.setPos(self.ui.ser_view.currentIndex-3, x-3)
                self.ui.ser_raw_view.view.addItem(self.mypoint)  
            
            profil=my_trame[x:x+1,:][0]
            self.ser_posx = x
            self.ui.ser_posx_lbl.setText(str(x))
            # affiche profile
            self.ui.spectre_view.clear()
            self.ui.spectre_view.setBackground('w')
            pen=pg.mkPen(color='blue',width=1.5)
            profile_name= 'Trame '+ str(trame_index)
            self.myplot = self.ui.spectre_view.plot(lamb, profil, pen=pen, name=profile_name, maxTickLength=-100, autoLevels=False)
            # affiche ligne verticale sur le fichier ser
            self.v_bar_pro.setPos(x)

    # tab proc
    #-------------------------------------------------------------------------
    
    def proc_open (self) :
        self.file_proc =''
        file_proc = QFileDialog.getOpenFileName(self, "Selectionner image ", self.working_dir, "Tous les fichiers png (*.png);;Fichiers disk png (*_disk.png);;Fichiers protus png (*_protus.png);;Fichiers clahe png (*_clahe.png);;Fichiers free (*_free.png);;Fichiers recon fits (*_recon*.fits);;Fichiers free fits (*_free.fits);;Fichiers cont fits (*_cont*.fits);;Fichiers fits (*.fits)",self.pattern)
        self.pattern = file_proc[1]
        if file_proc[0] != '' :
            self.file_proc=file_proc[0]
            self.proc_read()
            self.file_grid=self.file_proc
            self.grid_read()
            
    def proc_read (self):
            self.working_dir= self.get_dirpath(self.file_proc)
            self.ui.proc_filename_lbl.setText(self.file_proc)
            # recupere extension
            self.ext_proc = self.get_extension (self.file_proc)
            # lecture est fonction de l'extension
            if self.ext_proc == 'png' or self.ext_proc == 'tiff':
                # si png
                img_proc=cv2.imread(self.file_proc,cv2.IMREAD_UNCHANGED)
                if len(img_proc.shape) == 3 :
                    img_proc=cv2.cvtColor(img_proc,cv2.COLOR_BGR2RGB)
            if self.ext_proc== 'fits' :
                #si fits
                img_proc, self.header_proc=self.read_fits_image(self.file_proc)
                img_proc=np.array(img_proc,dtype='uint16')
                
            self.original_data=np.copy(img_proc)
            img_proc = np.fliplr(np.rot90(img_proc, 3))
            self.image_data=np.copy(img_proc)
            self.ui.proc_view.setImage(img_proc)
            iw,ih = img_proc.shape[0], img_proc.shape[1]
            self.ui.proc_img_width_lbl.setText(str(iw))
            self.ui.proc_img_height_lbl.setText(str(ih))
        
    
    def proc_apply (self) :
        # on part de l'image d'origine à chque fois
        img=np.copy(self.original_data)
        img_proc=np.copy(img)
        
        # clahe
        if not self.ui.proc_clahenone_radio.isChecked() :
            if self.ui.proc_clahelow_radio.isChecked() :
                self.clahe_level=1 
            else:
                if self.ui.proc_clahemedium_radio.isChecked() :
                    self.clahe_level=2 
                else :
                    self.clahe_level=3 
            img_proc=self.claheImage(img, self.clahe_level)
        #else :
            #img_proc=np.copy(self.original_data)
        
        # renforcement
        if not self.ui.proc_sharpnone_radio.isChecked() :
            if self.ui.proc_sharplow_radio.isChecked() :
                self.sharp_level=1 
            else:
                if self.ui.proc_sharpmedium_radio.isChecked() :
                    self.sharp_level=2 
                else :
                    self.sharp_level=3 
            img_proc=self.sharpenImage(img_proc, self.sharp_level)
        #else :
            #img_proc=np.copy(self.original_data)
        
        # couleur
        couleur=self.ui.proc_color_combo.currentText()
        if ( couleur !='Aucune' and couleur !='None') :
            img_proc=Colorise_Image(couleur, img_proc)
        
        # rotation
        if self.ui.proc_ang_text.text() !='' and self.ui.proc_ang_text.text() !='0' :
            try :
                ang_rot=float(self.ui.proc_ang_text.text())
                
                if self.ext_proc == "png" :
                    # rotation autour du centre de l'image
                    try :
                        baseline = os.path.basename(get_baseline(os.path.splitext(self.file_proc)[0]))
                        self.file_proc_log=self.working_dir+os.sep+baseline+"_log.txt"
                        
                        if not os.path.exists(self.file_proc_log):
                            # remonte d'un cran le chemin
                            parent_path = Path(self.working_dir).parent
                            self.file_proc_log=str(parent_path)+os.sep+baseline+"_log.txt"
                            
                        #self.file_proc_log = get_baseline(os.path.splitext(self.file_proc)[0]) + "_log.txt"
                        cx,cy,sr,ay1,ay2,ax1,ax2 = get_geom_from_log(self.file_proc_log)
                        diam=int(int(sr)*2)
                    except :
                        diam=0
                    cx = img_proc.shape[1]//2 
                    cy = img_proc.shape[0]//2
                    img_rot = img_rotate(img_proc, ang_rot, int(cx), int(cy), int(diam))
                    
                else :
                    try :
                        # rotation autour du centre de l'image
                        cx = img_proc.shape[1]//2 
                        cy = img_proc.shape[0]//2
                        diam = self.header_proc['SOLAR_R']*2
                        #cfx=self.header_proc['CENTER_X']
                        #cfy=self.header_proc['CENTER_Y']

                        img_rot = img_rotate(img_proc, ang_rot, int(cx), int(cy), diam)
                    except :
                        print(self.tr('Erreur fits'))
                       
                img_proc= np.copy(img_rot)
                #self.ui.proc_view.setImage(img_rot,autoRange=False)
            
            except :
                print(self.tr('Erreur angle de rotation'))
        
        img_proc = np.fliplr(np.rot90(img_proc, 3))
        self.ui.proc_view.setImage(img_proc, autoRange=False)
        
    def proc_helium(self):
        img=np.copy(self.original_data)
        #self.ext_proc=self.get_extension(self.file_proc)
        if self.ext_proc == 'fits' :        
            d = np.array(img, dtype='float64')-32767
            offset=-np.min(d)
            img=d+float(offset+100)
            img_uint=np.array((img), dtype='uint16')
            Seuil_bas=0 
            Seuil_haut=int(np.percentile(img_uint,99.99))
            if (Seuil_haut-Seuil_bas) != 0 :
                img_weak=seuil_image_force(img_uint, Seuil_haut, Seuil_bas)
            else:
                img_weak=np.array((img), dtype='uint16')
        else :
            img_weak=np.array((img), dtype='uint16')
        
        R = int(self.get_radius(self.file_proc))
        height, width = img.shape
        center = (width//2, height//2) # TODO lire les valeurs dans log ou entete fits
        
        if R !=0 :
            """
            seuil,mask = helium_seg(img, radius)
            belle_image, chull, neg_chull, BelleImage = helium_flat(img, seuil, mask)
            
            """
            result_image = corrige_trans_helium(img_weak, R)

            flag_add_conti = self.ui.proc_add_conti_check.isChecked()
            
            if flag_add_conti :
                coef=0.8
                # cherche fichier continuum _sum.fits dans complements ou en direct
                basefich= self.short_name(self.file_proc).split('.')[0][:-5]
                file_cont=self.working_dir+os.sep+'Complements'+os.sep+basefich+'_sum.fits'
                print(file_cont)
                try : 
                    moy, header=self.read_fits_image(file_cont)
                    moy=np.array(moy,dtype='uint16')
                    
                except :
                    try :
                        file_cont=self.working_dir+os.sep+os.sep+basefich+'_sum.fits'
                        moy, header=self.read_fits_image(file_cont)
                        moy=np.array(moy,dtype='uint16')
                        
                    except :
                        print(self.tr('Erreur ouverture fichier : ')+file_cont)
            else :
                coef=0.0
                moy=np.full((width, height), 0)
                
            # On ajoute le continuum méthode sunscan ou pas
            image1 = np.array(result_image, dtype=np.int32) 
            image2 = np.array(moy, dtype=np.int32)
            constant = 32767
            
            image2_transformed = np.where(image2 > 0, image2 - constant, 0)
            result_image = image1 + coef * image2_transformed
            result_image = np.clip(result_image, 0, 65535).astype(np.uint16)
            max_value = np.max(result_image)
            result_image = (result_image / max_value) * 65535.0
            result_image = result_image.astype(np.uint16)
            
            # etape supplémentaire de merge avec fond
            
            feather_width=15
            radius=R-feather_width-1

            # Create the circular mask
            mask = create_circular_mask((height, width), center, radius, feather_width)
            # Blend the images
            belle_image = blend_images(img_weak, result_image, mask)
            
            belle_image = np.fliplr(np.rot90(belle_image, 3))
            #self.ui.proc_view.setImage(belle_image,autoRange=False)
            
            
            """
            # on a l'image de continuum dans le tableau img_cont
            # il faut disk helium only /37267 * coef 1.32 + disk img_cont+ partie protus
            # applique mask sur image de continuum
            img_cont=img_cont*chull 
            #img_fond=img*neg_chull
            img_disk_helium= np.where( BelleImage>0, BelleImage-37267,0)
            coefA= 1
            coefB=0.1
            #img_transformed= (coef * img_disk_helium) + img_fond + img_cont
            img_transformed= (coefA * img_disk_helium) + (coefB * img_cont)
            img_transformed= np.clip(img_transformed,0,65535)
            img_finale=np.array (img_transformed, dtype='uint16')
            belle_image = np.fliplr(np.rot90(img_finale, 3))
            """
            """
            if flag_he_color :
                couleur="Helium"
                belle_image=Colorise_Image(couleur, belle_image)
            """
            
            self.ui.proc_view.setImage(belle_image,autoRange=False)
        else :
            print(self.tr("Erreur lecture rayon du disque"))
    
    def proc_magnet(self):
        img=np.copy(self.original_data)
        seuil,mask = pic_histo(img)
        img=np.rot90(img,1)
        belle_image, chull, neg_chull, BelleImage = helium_flat(img, seuil, mask)
        belle_image=np.rot90(belle_image,3)
        belle_image = np.fliplr(np.rot90(belle_image, 3))
        self.ui.proc_view.setImage(belle_image,autoRange=False)
        
        
    def proc_undo (self) :
        img_proc=self.original_data
        img_proc = np.fliplr(np.rot90(img_proc, 3))
        self.ui.proc_view.setImage(img_proc,autoRange=False)
        iw,ih = self.original_data.shape[0], self.original_data.shape[1]
        self.ui.proc_img_width_lbl.setText(str(ih))
        self.ui.proc_img_height_lbl.setText(str(iw))
        
        
    def proc_crop_test (self) :
        error=False
        if self.myROI !=[] :
            if self.myROI.scene() is  self.ui.proc_view.getView().scene() :
                self.ui.proc_view.removeItem(self.myROI)
        try :
            new_ih=int(self.ui.proc_crop_y_text.text())//2
            new_iw=int(self.ui.proc_crop_x_text.text())//2
        except :
            error=True
            print(self.tr("Erreur valeurs x ou y"))
            
        img_ih=int(self.ui.proc_img_width_lbl.text())
        img_iw=int(self.ui.proc_img_height_lbl.text())
        
        if new_ih > img_ih//2 or new_iw > img_iw//2 and error==False:
            error=True
            print(self.tr("Erreur valeurs x ou y"))
        if new_ih<=0 or new_iw<= 0 and error==False:
            error =True
            print(self.tr("Erreur valeurs x ou y"))
        
        if error == False :
            cx=int(self.ui.proc_img_width_lbl.text())//2
            cy=int(self.ui.proc_img_height_lbl.text())//2
            # (ih-50,iw-50), (100,100)
            self.myROI=pg.RectROI((cx-(new_iw),cy-(new_ih)), (2*new_iw,2*new_ih), centered=False,sideScalers=False, movable=False, resizable=False, rotatable=False)
            self.myROI.removeHandle(0)
            self.ui.proc_view.addItem(self.myROI)
                  
    
    def proc_crop (self) :
        error=False
        if self.myROI !=[] :
            if self.myROI.scene() is  self.ui.proc_view.getView().scene() :
                self.ui.proc_view.removeItem(self.myROI)
            
        try :
            new_ih=int(self.ui.proc_crop_y_text.text())//2
            new_iw=int(self.ui.proc_crop_x_text.text())//2
        except :
            error=True
            print(self.tr("Erreur valeurs x ou y"))
            
        img_ih=int(self.ui.proc_img_width_lbl.text())
        img_iw=int(self.ui.proc_img_height_lbl.text())
        
        if new_ih > img_ih//2 or new_iw > img_iw//2 and error==False:
            error=True
            print(self.tr("Erreur valeurs x ou y"))
        if new_ih<=0 or new_iw<= 0 and error==False:
            error =True
            print(self.tr("Erreur valeurs x ou y"))
        
        if error == False :
            cx=int(self.ui.proc_img_width_lbl.text())//2
            cy=int(self.ui.proc_img_height_lbl.text())//2
            my_img=self.ui.proc_view.image
            my_img=np.flipud(np.rot90(my_img))
            crop_img=my_img[cy-new_ih:cy+new_ih,cx-new_iw:cx+new_iw]
            flip_crop_img=np.fliplr(np.rot90(crop_img, 3))
            self.ui.proc_view.setImage(flip_crop_img,autoRange=False)
            self.ui.proc_img_width_lbl.setText(str(new_iw*2))
            self.ui.proc_img_height_lbl.setText(str(new_ih*2))
        
        
    def proc_saveas (self) :
        file_name,_=QFileDialog.getSaveFileName(self, self.tr("Sauver fichier "), self.working_dir, self.tr("Fichiers png (*.png);;Fichiers fits (*.fits) "))
        ext=self.get_extension(file_name)
        if file_name :
            print(file_name+' '+ext)
            myimage=self.ui.proc_view.image
            if ext == 'png' :
                levels= self.ui.proc_view.getLevels()
                if levels is not None:
                    min_val, max_val = levels
                    scaled = np.clip((myimage - min_val) / (max_val - min_val), 0, 1)
                    image_scaled = (scaled * 65535).astype(np.uint16)
                else:
                    image_scaled = myimage.astype(np.uint16)  # si pas de seuils appliqués
                
                myimage=np.flipud(np.rot90(image_scaled))
                if len(myimage.shape)==3 :
                    myimage=cv2.cvtColor(myimage, cv2.COLOR_BGR2RGB)
                
                cv2.imwrite(file_name, myimage)
            if ext == 'fits' :
                if len(myimage.shape)==3 :
                    print(self.tr("Fichier couleur, pas de conversion fits"))
                else :
                    # initialisation d'une entete fits (etait utilisé pour sauver les trames individuelles
                    hdr= fits.Header()
                    hdr['SIMPLE']='T'
                    hdr['BITPIX']=32
                    hdr['NAXIS']=2
                    hdr['NAXIS1'] = myimage.shape[1] # Width
                    hdr['NAXIS2'] = myimage.shape[0]# Height
                    hdr['BZERO']=0
                    hdr['BSCALE']=1
                    hdr['BIN1']=1
                    hdr['BIN2']=1
                    hdr['EXPTIME']=0
                    # pas de date
                    
                    myimage=(np.rot90(myimage))
                    self.save_fits_image(file_name, myimage, hdr, nb_bytes=16)

            
    def proc_angP (self) :
        if self.ext_proc == 'png' :
            try :
                baseline = os.path.basename(get_baseline(os.path.splitext(self.file_proc)[0]))
                self.file_proc_log=self.working_dir+os.sep+baseline+"_log.txt"
                
                if not os.path.exists(self.file_proc_log):
                    # remonte d'un cran le chemin
                    parent_path = Path(self.working_dir).parent
                    self.file_proc_log=str(parent_path)+os.sep+baseline+"_log.txt"
                
                _,dateutc = get_time_from_log(self.file_proc_log)
                dateobs=dateutc[0]+'T'+dateutc[1]
            except :
                print('Erreur fichier _log txt')
        else :
            dateobs= self.header_proc['DATE-OBS']
            
        try :
            print(dateobs)
            (angP,B0, L0, Carr) = angle_P_B0(dateobs)
        except :
            print(self.tr('Erreur calcul angle P'))
            
        self.ui.proc_ang_text.setText(str(angP))
        
                
    def proc_infos(self):
        try :
            self.myinfos = infos_dlg()
            if self.ext_proc == 'png' :
                baseline = os.path.basename(get_baseline(os.path.splitext(self.file_proc)[0]))
                self.file_proc_log=self.working_dir+os.sep+baseline+"_log.txt"
                
                if not os.path.exists(self.file_proc_log):
                    # remonte d'un cran le chemin
                    parent_path = Path(self.working_dir).parent
                    self.file_proc_log=str(parent_path)+os.sep+baseline+"_log.txt"
                    
                #self.file_proc_log = get_baseline(os.path.splitext(self.file_proc)[0]) + "_log.txt"
                self.myinfos.display_infos_log(self.file_proc_log)
            else :
                self.myinfos.display_infos_fits(self.header_proc)
                
            
        except :
            #myinfos.ui.close()
            print(self.tr('Pas de fichier : ') + self.file_proc_log)
        
                        
            
    # tab grid
    #-------------------------------------------------------------------------
    
    def grid_open (self) :
        self.file_grid =''
        #self.ui.grid_view.clear()
        try :
            if self.plotitem :
                for p in self.plotitem :
                    if p.scene() is  self.ui.grid_view.getView().scene() :
                        self.ui.grid_view.view.removeItem(p)
        except :
            pass
            
        file_grid = QFileDialog.getOpenFileName(self, "Selectionner image ", self.working_dir, "Fichiers png (*.png);;Fichiers fits (*.fits)")
        if file_grid != ('',''):
            self.file_grid=file_grid[0]
            self.grid_read()
            self.file_proc=self.file_grid
            self.proc_read()
            
    def grid_read (self):
            self.filigranes =[]
            self.grid_dist_cancel()
            self.working_dir= self.get_dirpath(self.file_grid)
            self.ui.grid_filename_lbl.setText(self.file_grid)
            # recupere extension
            self.ext_grid = self.get_extension (self.file_grid)
            # lecture est fonction de l'extension
            if self.ext_grid == 'png' or self.ext_grid == 'tiff':
                # si png noir et blanc
                img_grid=cv2.imread(self.file_grid,cv2.IMREAD_UNCHANGED)
                if len(img_grid.shape) == 3 :
                    img_grid=cv2.cvtColor(img_grid, cv2.COLOR_BGR2RGB)
            
            if self.ext_grid == 'fits' :
                #si fits
                img_grid, hdr=self.read_fits_image(self.file_grid)
                img_grid=np.array(img_grid,dtype='uint16')              
           
            img_grid2 = np.fliplr(np.rot90(img_grid, 3))
            self.image_data=np.copy(img_grid2)
            self.ui.grid_view.setImage(img_grid2)
            try :
                if self.ext_grid == "fits" :
                    mydate=hdr['DATE-OBS']
                    self.hdr=hdr
                else :
                    baseline = os.path.basename(get_baseline(os.path.splitext(self.file_grid)[0]))
                    self.file_grid_log=self.working_dir+os.sep+baseline+"_log.txt"
                    
                    if not os.path.exists(self.file_grid_log):
                        # remonte d'un cran le chemin
                        parent_path = Path(self.working_dir).parent
                        self.file_grid_log=str(parent_path)+os.sep+baseline+"_log.txt"
                    #self.file_grid_log = get_baseline(os.path.splitext(self.file_grid)[0]) + "_log.txt"
                    _,dateutc = get_time_from_log(self.file_grid_log)
                    mydate=dateutc[0]+'T'+dateutc[1]
                self.ui.grid_date_text.setText(mydate)
                angP, paramB0, longL0, RotCarr = angle_P_B0(mydate)
                #self.ui.grid_angP_text.setText(angP)
            except :
                pass
            
            self.img_grid=img_grid
            self.img_grid_orig=np.copy(img_grid)
            
    def grid_plot (self) :
        
            if self.img_grid.any() :
                mydate = self.ui.grid_date_text.text()
                # il faudra faire un test de format
                if self.ui.grid_label_checkbox.isChecked() :
                    graduation_on = True
                else :
                    graduation_on = False
                
                color_index = self.ui.grid_color_combo.currentIndex()
                text_color_list = [(250, 250, 0,0x80), (250, 250, 250,0x80), (250, 250, 250,0x80)]
                text_color= text_color_list[color_index]
                pen_color_list = [pg.mkPen(QtGui.QColor(250,250,0,0x60),width=1), pg.mkPen(QtGui.QColor(0,0,0,0x60),width=1), pg.mkPen(QtGui.QColor(250,250,250,0x60),width=1)]
                mypen = pen_color_list [color_index]
                
                if self.plotitem :
                    for p in self.plotitem :
                        if p.scene() is  self.ui.grid_view.getView().scene() :
                            self.ui.grid_view.view.removeItem(p)
                        
                iw,ih = self.img_grid.shape[0], self.img_grid.shape[1]
                
                try :
                    if self.ext_grid == "fits" :
                        xc = self.hdr['CENTER_X']
                        yc = self.hdr['CENTER_Y']
                        radius = self.hdr['SOLAR_R']
                    else :
                        cx,cy,sr,ay1,ay2,ax1,ax2 = get_geom_from_log(self.file_grid_log)
                        xc=int(cx)
                        yc=int(cy)
                        radius = int(sr)
                    
                    # inversion axe Y
                    yc=ih-yc
                    r=radius
                    
                    P_,B0_,L0_, Rot_Carr=angle_P_B0 (mydate)
                    P_disp=P_
                    
                    if self.ui.grid_Pdone_checkbox.isChecked() :
                        P_=0
                        
                    P_rad=math.radians(float(P_))
                    B0_rad=math.radians(float(B0_))
                    
                    # draw data coin gauche
                    font = QtGui.QFont('Arial', 6)
                    plot_text = pg.TextItem(text = mydate, color=text_color)
                    h_text=plot_text.boundingRect().height()+10
                    self.plotitem.append(plot_text)
                    self.ui.grid_view.view.addItem(plot_text)
                    plot_text.setPos(50, 10)
                    plot_text.setFont(font)
                    plot_text = pg.TextItem(text = 'P = '+ P_disp+' °', color=text_color)
                    self.plotitem.append(plot_text)
                    self.ui.grid_view.view.addItem(plot_text)
                    plot_text.setPos(50, 10+10+h_text)
                    plot_text.setFont(font)
                    plot_text = pg.TextItem(text = 'B0 = '+ B0_+' °', color=text_color)
                    self.plotitem.append(plot_text)
                    self.ui.grid_view.view.addItem(plot_text)
                    plot_text.setPos(50, 3*10+2*h_text)
                    plot_text.setFont(font)
                    plot_text = pg.TextItem(text = 'L0 = '+ L0_+' °', color=text_color)
                    self.plotitem.append(plot_text)
                    self.ui.grid_view.view.addItem(plot_text)
                    plot_text.setPos(50, 4*10+3*h_text)
                    plot_text.setFont(font)
                    
                    
                    #draw circle
                    angle = np.linspace( 0 , 2 * np.pi , 150 ) 
                    x_cercle = xc+radius * np.cos( angle ) 
                    y_cercle = yc+radius * np.sin( angle ) 
                    #pen=pg.mkPen(QtGui.QColor(250,250,0,0x60),width=1)
                    mycircle = pg.PlotCurveItem(x_cercle,y_cercle, pen=mypen)
                    self.plotitem.append(mycircle)
                    self.ui.grid_view.view.addItem(mycircle)
                    
                    B=np.linspace(-90, 90,39)
                    B_rad=[ math.radians(a) for a in B]
                    
                    L=np.linspace(-180,180,37)
                    L_rad=[ math.radians(a) for a in L]
                    
                    # L=0
                    
                    itemindex=0
                    
                    for ll in L_rad :
                        X=np.array([r*math.cos(a)*math.sin(ll) for a in B_rad])
                        Y=[r*math.cos(a)*math.cos(ll) for a in B_rad]
                        Z=[r*math.sin(a) for a in B_rad]
                        
                        zz=[a*math.cos(B0_rad) for a in Z]
                        yy=[a*math.sin(B0_rad) for a in Y]
                        zz=np.array(zz)
                        yy=np.array(yy)
                        
                        xp1= xc+(zz-yy)*math.sin(P_rad)
                        xp2=np.array(X)*math.cos(P_rad)
                        xp=np.array(xp1)+np.array(xp2)
                        
                        yp1= yc- (zz-yy)*math.cos(P_rad)
                        yp2= np.array(X)*math.sin(P_rad)
                        yp=np.array(yp1)+np.array(yp2)   
                        
                        t=((xp-xc)**2+(yp-yc)**2)
                        tt=abs(t-r**2)
                        itemindex=np.argmin(tt)
                        
                        
                        if float(B0_) >=0 : 
                            xpp=xp[itemindex:]
                            ypp=yp[itemindex:]
                        else:
                            xpp=xp[:itemindex]
                            ypp=yp[:itemindex]
                        
                        if itemindex ==0 or itemindex==38:
                            xpp=xp
                            ypp=yp
                            
                        if (itemindex == (len(xp)-1) or itemindex==0 ) and abs(math.degrees(ll))>90:
                            xpp=[xp[0]]
                            ypp=[yp[0]]
                            itemindex=1000
                        
                        #print(round(math.degrees(ll)), itemindex)
                        myplot = pg.PlotCurveItem(xpp,ypp, pen=mypen)
                        self.plotitem.append(myplot)
                        self.ui.grid_view.view.addItem(myplot)
                    
                    # Trace les tropiques
                    B=np.linspace(-90, 90,19)
                    B_rad=[ math.radians(a) for a in B]
                    
                    L=np.linspace(-180,180,49)
                    L_rad=[ math.radians(a) for a in L]
                    
                    for bb in B_rad :
                        
                        Z=np.array([r*math.sin(bb) for a in L_rad])
                        X=np.array([r*math.sin(a)*math.cos(bb) for a in L_rad])
                        Y=np.array([r*math.cos(a)*math.cos(bb) for a in L_rad])
                        
                        zz=np.array([a*math.cos(B0_rad) for a in Z])
                        yy=np.array([a*math.sin(B0_rad) for a in Y])
                       
                        
                        xp1=xc+(zz-yy)*math.sin(P_rad)
                        xp2=np.array(X)*math.cos(P_rad)
                        xp= np.array(xp1)+np.array(xp2)
                        
                        yp1=yc- (zz-yy)*math.cos(P_rad)
                        yp2=np.array(X)*math.sin(P_rad)
                        yp= np.array(yp1)+np.array(yp2)
                        
                        t=((xp-xc)**2+(yp-yc)**2)
                        tt=abs(t-r**2)
                    
                        itemindex=np.argmin(tt)
                        
                    
                        if itemindex > (len(xp)-1)/2 :
                            itemindex=len(xp)-1-itemindex
                            #print(xpp)
                        
                        if itemindex != 0 :
                            xpp=xp[itemindex:-itemindex]
                            ypp=yp[itemindex:-itemindex]
                           
                        else:
                            xpp=xp
                            ypp=yp
                        #print(math.degrees(bb),itemindex)
                        #plt.plot(xpp,ypp,linestyle="-", color=couleur_positive, linewidth=largeur_ligne, alpha=opacity)
                        #pen=pg.mkPen(QtGui.QColor(250,250,0),width=1)
                        myplot = pg.PlotCurveItem(xpp,ypp, pen=mypen)
                        self.plotitem.append(myplot)
                        self.ui.grid_view.view.addItem(myplot)
                    
                        if graduation_on :
                            if len(xpp)!=1 and abs(math.degrees(bb))!=90:
                                lx1=[xpp[0], xpp[0]-20*math.cos(bb+P_rad)]
                                ly1=[ypp[0],ypp[0]-20*math.sin(bb+P_rad)]
                                #plt.plot(lx1,ly1, color='white', linestyle='-', linewidth=0.2)
                                myplot = pg.PlotCurveItem(lx1,ly1, pen=mypen)
                                self.plotitem.append(myplot)
                                self.ui.grid_view.view.addItem(myplot)
                                
                                #plt.text(lx1[0]-50*math.cos(bb), ly1[0]-50*math.sin(bb), 
                                #         str(round(math.degrees(bb))), fontsize=3, color='yellow',
                                #        horizontalalignment='center', verticalalignment='center')
                                plot_text = pg.TextItem(text = str(round(math.degrees(bb))), color=text_color, anchor=(0.5,0.5))
                                self.plotitem.append(plot_text)
                                self.ui.grid_view.view.addItem(plot_text)
                                plot_text.setPos(lx1[0]-50*math.cos(bb+P_rad),ly1[0]-50*math.sin(bb+P_rad))
                                plot_text.setFont(font)
                                lx2=[xpp[-1], xpp[-1]+20*math.cos(bb+P_rad)]
                                ly2=[ypp[-1],ypp[-1]-20*math.sin(bb+P_rad)]
                                #plt.plot(lx2,ly2, color='white', linestyle='-', linewidth=0.2)
                                myplot = pg.PlotCurveItem(lx2,ly2, pen=mypen)
                                self.plotitem.append(myplot)
                                self.ui.grid_view.view.addItem(myplot)
                                #plt.text(lx2[0]+50*math.cos(bb), ly2[0]-50*math.sin(bb), 
                                #        str(round(math.degrees(bb))), fontsize=3, color='yellow',
                                #        horizontalalignment='center', verticalalignment='center')
                                plot_text = pg.TextItem(text = str(round(math.degrees(bb))), color=text_color, anchor=(0.5,0.5))
                                self.plotitem.append(plot_text)
                                self.ui.grid_view.view.addItem(plot_text)
                                #plot_text.setPos(lx2[0]-50*math.cos(bb+P_rad),ly2[0]+20*math.sin(bb+P_rad))
                                plot_text.setPos(lx2[0]+50*math.cos(bb+P_rad),ly2[0]-50*math.sin(bb+P_rad))
                                plot_text.setFont(font)
                except :
                    print(self.tr("Mots clefs manquants dans entête fits"))
                 
    def grid_gong(self):
        # cela n'a du sens que si on a deja une image _recon
        fits_dateobs = self.ui.grid_date_text.text()
        if fits_dateobs!='' :
            filename = self.ui.grid_filename_lbl.text()
            #fname='_'+self.get_basename(self.short_name(self.serfiles[-1]))+'_disk.png'
            #filename= self.working_dir+os.sep+fname
        
            self.mygong=gong_wnd()
            
            datemonth=fits_dateobs.split('T')[0].replace('-','')[:6]
            dateday=fits_dateobs.split('T')[0].replace('-','')
            r1="https://gong2.nso.edu/HA/hag/"+datemonth+"/"+dateday+"/"
            Vo_req=r1

            reponse_web=rq.get(Vo_req)
            sun_meudon=reponse_web.text.split("\n")
            t=sun_meudon[11].split('href=')[1].split(">")[0]
            t=t.replace('"','')
            #print(r1+t)
            url = r1+t 
            img_data = requests.get(url).content
            # pour faire une image pour detecter les inversions
            #nparr =np.frombuffer(img_data,np.uint8)
            #img_gong=cv2.imdecode(nparr,cv2.IMREAD_GRAYSCALE)
            
            self.mygong.show()
            
            # geometry écrans
            screen_geom = QtGui.QGuiApplication.primaryScreen().availableGeometry()
            self.dpr = QtGui.QGuiApplication.primaryScreen().devicePixelRatio()
            self.myscreen_w = int(screen_geom.right()*self.dpr)
            self.myscreen_h = int(screen_geom.bottom()*self.dpr)
            
            w_w=self.myscreen_w*0.4
            #r=self.myscreen_h/self.myscreen_w
            w_h = (w_w*0.5)+9
            if w_h > self.myscreen_h :
                w_w=w_h*2
            self.mygong.ui.resize(int(w_w), int(w_h))
            

            pixmap = QtGui.QPixmap()
            pixmap.loadFromData(img_data)
            lbl_w, lbl_h= (self.mygong.ui.gong_gongimg_lbl.width(),self.mygong.ui.gong_gongimg_lbl.height())
            pixmap.scaled(lbl_w, lbl_h,Qt.IgnoreAspectRatio)
            self.mygong.ui.gong_gongimg_lbl.setPixmap(pixmap)
            self.mygong.ui.gong_gongimg_lbl.adjustSize()
            #web.open(r1+t)
            if os.path.exists(filename):
                #web.open(filename)
                #pixmap2 = QtGui.QPixmap(filename)
                img_disk=cv2.imread(filename,cv2.IMREAD_UNCHANGED)
                ih, iw = img_disk.shape
                if ih != iw :
                    # a priori image toujours plus large que haute...
                    pad_h= (iw-ih)//2
                    pad_zone = np.zeros((pad_h,iw), dtype= 'uint16')
                    img_disk= np.concatenate((pad_zone,img_disk,pad_zone))
                img_disk_8bits=(img_disk/256).astype(np.uint8)
                myqimage = QtGui.QImage(img_disk_8bits, iw, iw ,iw, QtGui.QImage.Format_Grayscale8)
                pixmap2= QtGui.QPixmap.fromImage(myqimage)
                lbl_w, lbl_h= (self.mygong.ui.gong_myimg_lbl.width(),self.mygong.ui.gong_myimg_lbl.height())
  
                pixmap2.scaled(lbl_w, lbl_w,Qt.IgnoreAspectRatio)
                self.mygong.ui.gong_myimg_lbl.setPixmap(pixmap2)
                self.mygong.ui.gong_myimg_lbl.adjustSize()
            
            
            """
            try :
                # detection des inversions - uniquement sur disque entier et sur H-alpha
                inversion = gong_orientation_auto(img_gong, img_disk)
                #print("Inversions : "+inversion)
                self.mygong.update_inversions(inversion)
                self.mygong.ui.finished.connect(self.ori_get_inversions)
            except:
                print('Erreur détection inversions')  
            """
        else :
            print("Pas de fichier sélectionné")   
    
    def grid_gong2(self):
        #fits_dateobs=self.hdr['DATE-OBS']
        fits_dateobs = self.ui.grid_date_text.text()
        filename=self.ui.grid_filename_lbl.text()
        curr_dir=self.working_dir
        gong (fits_dateobs, filename, curr_dir)
        
    def grid_dg (self) :
        img=self.ui.grid_view.image
        img=np.flipud(img)
        self.ui.grid_view.setImage(img, autoLevels=False, autoRange=False)
        self.img_grid=img
        
    def grid_hb (self) :
        img=self.ui.grid_view.image
        img=np.fliplr(img)
        self.ui.grid_view.setImage(img, autoLevels=False, autoRange=False)
        self.img_grid=img
        
    def grid_rotate (self) :
        angle=float(self.ui.grid_angP_text.text())
        if self.ext_grid == 'fits' :
            centreX=self.hdr['CENTER_X']
            centreY=self.hdr['CENTER_Y']
            diam= int(self.hdr['SOLAR_R']*2)
        else :
            try :
                cx,cy,sr,ay1,ay2,ax1,ax2 = get_geom_from_log(self.file_grid_log)
                centreX=int(cx)
                centreY=int(cy)
                diam=int(int(sr)*2)
            except:
                print(self.tr('Fichier _log.txt non trouvé'))
            
        img=np.copy(self.img_grid)
        #print(angle, centreX, centreY)
        centreX=img.shape[1]//2 
        centreY=img.shape[0]//2
        img_rot = img_rotate(img, angle, centreX, centreY, diam)
        self.ui.grid_view.setImage(img_rot)
        
    def grid_annuler (self) :
        try :
            if self.plotitem :
                for p in self.plotitem :
                    if p.scene() is  self.ui.grid_view.getView().scene() :
                        self.ui.grid_view.view.removeItem(p)
        except :
            pass
        img=self.img_grid_orig
        self.ui.grid_view.setImage(img)
        self.img_grid=img
        
    
    def grid_saveas (self) :
        file_name,_=QFileDialog.getSaveFileName(self, self.tr("Sauver fichier png"), self.working_dir, self.tr("Fichiers png (*.png);;Tous les fichiers (*)"))
        if file_name :
            print(file_name)
            # create an exporter instance, as an argument give it
            # the item you wish to export
            exporter = ImageExporter(self.ui.grid_view.getImageItem())
            # set export parameters if needed
            exporter.parameters()['height'] = 800   # (note this also affects height parameter)
            # save to file
            exporter.export(file_name)
    
    def grid_fili_cancel(self):
        for item in self.filigranes:
            if item.scene() is  self.ui.grid_view.getView().scene() :
                self.ui.grid_view.getView().removeItem(item)
        self.filigranes.clear()
    
    def grid_fili_display(self) :
              
        fili_text = self.ui.grid_fili_text.toPlainText()
        # Création d'un texte qui sera "attaché" à une coordonnée de l'image
        text_item = pg.TextItem(fili_text, color='ivory', anchor=(0, 1))
        rect = text_item.boundingRect()
        #largeur = rect.width()
        hauteur = rect.height()
        pos = self.ui.grid_fili_combo.currentIndex()
        if pos == 1 : # Haut
            xpos =50
            ypos=100+hauteur
        if pos == 0 : # Bas
            xpos=50
            ypos = self.img_grid.shape[0]-20
        text_item.setPos(xpos, ypos)  # Position dans les coordonnées de l'image x,y
        self.filigranes.append(text_item)
        self.ui.grid_view.getView().addItem(text_item)  # Ajout à la vue
        
        
        
    def grid_dist (self) :
        mid_deg_input = int(self.ui.grid_ang_dist_text.text())
        mid_deg = -mid_deg_input+90
        try :
            if self.ext_grid == "fits" :
                xc = self.hdr['CENTER_X']
                yc = self.hdr['CENTER_Y']
                rsun_pixels = self.hdr['SOLAR_R']
            else :
                cx,cy,sr,ay1,ay2,ax1,ax2 = get_geom_from_log(self.file_grid_log)
                xc=int(cx)
                yc=int(cy)
                rsun_pixels = int(sr)
                if cy == 0 or sr == 0 :
                    print (self.tr("Erreur lecture rayon disque solaire"))
                    return
        except :
            print (self.tr("Erreur lecture rayon disque solaire"))
        
        # Créer les arc de cercle
        rsun_km = 696340  # rayon réel du Soleil en km
        
        angle_step_deg = 1  # résolution angulaire
        step_km = 50000  # espacement des arc de cercle
        km_per_pixel = rsun_km / rsun_pixels
        
        # offset si disque partiel
        ih, iw = self.img_grid.shape
        #x0= xc-(iw//2)
        yc0= ih-yc

        self.ui.grid_view.getView().setAspectLocked(True)
        # Créer une police plus petite
        font = QtGui.QFont()
        font.setPointSize(6)  # taille en points (ex : 8 pt)
        
        if len(self.img_grid.shape)==3 :
            width,height,_ = self.img_grid.shape
        else :
            width,height = self.img_grid.shape
        
        mid_theta=math.radians(mid_deg)
        
        for k in range(1,5) :
            r_km = rsun_km+k*step_km
            r_pix = r_km / km_per_pixel
            start_deg = mid_deg-(k*2)
            end_deg = mid_deg+(k*2)
            
            # Créer le chemin de l'arc
            path = QtGui.QPainterPath()
            first = True
            for angle_deg in range(start_deg, end_deg + 1, angle_step_deg):
                theta = math.radians(angle_deg)
                x = xc + r_pix * math.cos(theta)
                y = yc0 - r_pix * math.sin(theta)  # y vers le bas
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)
                       
            x_lab =  xc + (r_pix * math.cos(math.radians(start_deg)))
            y_lab = yc0 - (r_pix * math.sin(math.radians(start_deg)))      
            
            arc_item = QGraphicsPathItem(path)
            arc_item.setPen(pg.mkPen(QtGui.QColor(150, 150, 150) , width=1))
            self.circle_list.append(arc_item)
            self.ui.grid_view.getView().addItem(arc_item)

            
            if mid_deg_input < 0 :
                mid_deg2=mid_deg_input+360
            else :
                mid_deg2=mid_deg_input

            # Ajoute un label à l’extrémité
            if mid_deg2 >=0 and mid_deg2<=90:
                my_anchor =(0,0.5)
            elif mid_deg2>90 and mid_deg2<=180 :
                my_anchor =(0,0.5)  # my_anchor =(1,0)
            elif mid_deg2 >180 and mid_deg2 <=270 :
                my_anchor = (0,0.5) # my_anchor = (1,1)
            elif mid_deg2>270 and mid_deg2 <360  :
                my_anchor = (0,0.5) # my_anchor = (0,1)
            
            
           
            if (k+1)%2 :
                label = pg.TextItem(f"{k*step_km} km", color='ivory', anchor=my_anchor)
                label.setFont(font)
                label.setPos(x_lab, y_lab)
                #label.setRotation(-start_deg+91)
                label.setRotation((-mid_deg+(2*2)+95))
                self.label_list.append(label)
                self.ui.grid_view.getView().addItem(label)
            
        # Rayon de départ : bord du disque
        
        r_start = rsun_pixels+5
        
        # Rayon de fin : dernier arc + 5 pixels
        r_end = r_pix + 1  # r_pix vient de la dernière itération moins un step
        
        # Coordonnées du point de départ
        x_start = xc + r_start * math.cos(mid_theta)
        y_start = yc0 - r_start * math.sin(mid_theta)

        
        # Coordonnées du point d’arrivée
        x_end = xc + r_end * math.cos(mid_theta)
        y_end = yc0 - r_end * math.sin(mid_theta)
        
        
        # Tracer la ligne
        from PySide6.QtWidgets import QGraphicsLineItem
        line = QGraphicsLineItem(x_start, y_start, x_end, y_end)
        line.setPen(pg.mkPen('w', width=1))
        self.line_list.append(line)
        self.ui.grid_view.getView().addItem(line)
             
            
    def grid_dist_cancel (self) :
        vb = self.ui.grid_view.getView()
        try:
            for item in self.circle_list:
                if item.scene() is vb.scene():
                    self.ui.grid_view.getView().removeItem(item)
            self.circle_list.clear()
        except :
            pass
        try :
            for item in self.label_list:
                if item.scene() is vb.scene():
                    self.ui.grid_view.getView().removeItem(item)
            self.label_list.clear()
        except :
            pass
        try :
            for item in self.line_list:
                if item.scene() is vb.scene():
                    self.ui.grid_view.getView().removeItem(item)
        except :
            pass
    
    
    def grid_terre (self):
        try :
            flag_do = True
            if self.ext_grid == "fits" :
                rsun_pixels = self.hdr['SOLAR_R']
            else :
                cx,cy,sr,ay1,ay2,ax1,ax2 = get_geom_from_log(self.file_grid_log)
                rsun_pixels = int(sr)
                if sr == 0 : flag_do = False
        except :
            print (self.tr("Erreur lecture rayon disque solaire"))
            flag_do = False
        
        if flag_do :
            # Créer les cercles concentriques
            rsun_km = 696340  # rayon réel du Soleil en km
            km_per_pixel = rsun_km / rsun_pixels
            # Rayon terrestre à l’échelle
            r_earth_km = 6371
            r_earth_px = r_earth_km / km_per_pixel
            
            # Charger l’image de la Terre
            pixmap = QtGui.QPixmap(self.img_earth)  # Assure-toi que le fichier est dans le bon dossier
            
            
            # Redimensionner l’image à 2*r_earth_px (diamètre)
            diameter = max(2, int(round(2 * r_earth_px)))
            scaled_pixmap = pixmap.scaled(diameter, diameter, Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.FastTransformation)
            
            # Créer l’objet graphique
            earth_item = QGraphicsPixmapItem(scaled_pixmap)
            self.terre_list.append(earth_item)
            
            if len(self.img_grid.shape)==3 :
                width,height,_ = self.img_grid.shape
            else :
                width,height = self.img_grid.shape
                
            # Position en bas à droite (avec marge) ou en haut à gauche
            margin = 100
            if self.ui.grid_terre_combo.currentIndex()== 0 : # haut
                x_earth = width - scaled_pixmap.width() - margin
                y_earth = margin
                my_anchor = (0.5,1)
                x_lab = x_earth+(scaled_pixmap.width()//2)
                y_lab = y_earth+2
                
            else :
                x_earth = width - scaled_pixmap.width() - margin
                y_earth = height - scaled_pixmap.height() - margin
                my_anchor = (0.5,0)
                x_lab = x_earth+(scaled_pixmap.width()//2)
                y_lab = y_earth-2
            
            earth_item.setPos(x_earth, y_earth)  
            
            # Créer une police plus petite
            font = QtGui.QFont()
            font.setPointSize(6)  # taille en points (ex : 8 pt)
            label_terre = pg.TextItem(self.tr("Terre"), color='ivory', anchor=my_anchor)
            label_terre.setFont(font)
            label_terre.setPos(x_lab, y_lab)
            self.terre_list.append(label_terre)
            self.ui.grid_view.getView().addItem(label_terre)
            
            self.ui.grid_view.getView().addItem(earth_item)
    
    def grid_terre_cancel (self) :
        vb = self.ui.grid_view.getView()
        try:
            for item in self.terre_list:
                if item.scene() is vb.scene():
                    self.ui.grid_view.getView().removeItem(item)
            self.terre_list.clear()
        except :
            pass
    
    
    
    #--------------------------------------------------------------------------
    # fonctions utilitaires
    #--------------------------------------------------------------------------
     
    
    def read_fits_image(self, file_name):
        with fits.open(file_name,memmap=False) as hdul:
            data = hdul[0].data
            header = hdul[0].header
            
            # ne fait pas ce decalage
           
            if np.min(data) < 0 :
                offset=32767
                data=data+float(-np.min(data))
                data=data.astype(np.uint16)
            
            data=np.flipud(data)
            
        return data, header
    
    def save_fits_image (self, name, data, hdr, nb_bytes):
        if nb_bytes == 16 :
            data = np.array( data, dtype='uint16')   # conversion en flottant 32 bits
        if nb_bytes == 32 :
            data = data.astype(np.float32)   # conversion en flottant 32 bits
        
        DiskHDU = fits.PrimaryHDU(data, hdr)
        DiskHDU.writeto(name, overwrite='True')
        
    def save_png_image (self, name, data):
        data = np.array( data, dtype='uint16')   # conversion en flottant 32 bits
        cv2.imwrite(name, data)
    
    def read_settings(self):
        settings=QSettings("Desnoux Buil", "inti_partner")
        self.ui.restoreGeometry(settings.value("MainWindow/geometry"))
        self.ui.restoreState(settings.value("MainWindow/windowState"))
        if settings.value("App/lang") is not None :
            self.langue=settings.value("App/lang")
        else :
            self.langue='FR'
            
        if settings.value("App/tab_index") is not None :
            self.current_tab= settings.value("App/tab_index")
        else :
            self.current_tab=0
        
        if settings.value("App/inti") is not None :
            self.inti_dir= settings.value("App/inti")
        else :
            self.inti_dir = ''
            
        if self.ui.dock_console.isFloating() :
            dock_geometry = self.ui.dock_console.geometry()
            visible = any (screen.geometry().intersects(dock_geometry) for screen in QtGui.QGuiApplication.screens())
            if not visible :
                screen_geom = QtGui.QGuiApplication.primaryScreen().availableGeometry()
                new_geom = QRect (screen_geom.x()+50, screen_geom.y()+50,dock_geometry.width(), dock_geometry.height())
                self.ui.dock_console.setGeometry(new_geom)
    
    
    def write_settings(self) :
        # force docks non floating
        self.ui.main_dock.setFloating(False)
        #self.ui.dock_console.setFloating(False)
        #self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.ui.main_dock)
        #self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.ui.dock_console)
        
        # sauve settings
        settings=QSettings("Desnoux Buil", "inti_partner")
        settings.setValue("MainWindow/geometry", self.ui.saveGeometry())
        settings.setValue("MainWindow/windowState", self.ui.saveState())
        settings.setValue("App/lang", self.langue)
        settings.setValue("App/tab_index", self.ui.tab_main.currentIndex())
        settings.setValue("App/inti", self.inti_dir)
        

    
    
    def name_to_png (self,filename):
        # retire extension fits pour ajouter extension png
        name_png=os.path.splitext(filename)[0]+'.png'
        #print(name_png)
        return name_png

    def file_exist(name):    
        if not os.path.exists(name):
            print('ERROR: File ' + name + ' not found.')
            sys.exit(1)
            
    def short_name(self,file_name):
        #f_short=file_name.split('/')[-1]
        f_short=os.path.split(file_name)[1]
        return f_short
    
    def racine_name(self,file_name):
        f_short=os.path.split(file_name)[1]
        f_racine=f_short.split('.')[0]
        return f_racine
    
    def get_dirpath(self,file_name):
        dir_path=os.path.split(file_name)[0]
        #print('dir : ', dir_path)
        return dir_path
    
    def get_extension(self, file_name) :
        pos=file_name.rfind('.')
        #ext=os.path.split(file_name)[1].split('.')[1]
        ext = file_name[pos+1:]
        return ext
    
    def get_radius(self,filename) :
        ext=self.get_extension(filename)
        if ext=="fits" :
            img,hdr=self.read_fits_image(filename)
            try :
                radius=hdr["SOLAR_R"]
            except :
                print("Erreur entete fits")
                radius=0 
        if ext=="png" :
            filename_short = self.short_name(filename)
            if filename_short.find('sunscan')!= -1 :
                filename_short=filename_short.replace('sunscan', '_scan')
            try :
                baseline = os.path.basename(get_baseline(os.path.splitext(filename_short)[0]))
                file_log=self.working_dir+os.sep+baseline+"_log.txt"
                
                if not os.path.exists(file_log):
                    # remonte d'un cran le chemin
                    parent_path = Path(self.working_dir).parent
                    file_log=str(parent_path)+os.sep+baseline+"_log.txt"
                
                cx,cy,sr,ay1,ay2,ax1,ax2 = mo.decode_log(file_log)
                radius= sr
            except :
                print("Erreur _log.txt")
                radius=0
        print("radius : ", radius)
        return radius

# ----------------------------------------------------------------------------
# class new window to display image floating
#-----------------------------------------------------------------------------

class img_wnd(QMainWindow) :
    
    on_ferme = Signal()
    
    def __init__(self, working_dir):
       
        #super().__init__(parent)
        super(img_wnd, self).__init__()
        
        
        #fichier GUI par Qt Designer
        loader = QUiLoader()
        loader.registerCustomWidget(ImageView)
        ui_file_name=resource_path('img_qt.ui')
        ui_file = QFile(ui_file_name)
        
        if not ui_file.open(QIODevice.ReadOnly):
            print(f"Cannot open {ui_file_name}: {ui_file.errorString()}")
            sys.exit(-1)
        
        self.ui = loader.load(ui_file)
        
        ui_file.close()
        
        self.ui.saveas_btn.clicked.connect(self.saveas)
        self.ui.open_in_btn.clicked.connect(self.open_in_tab)
        self.working_dir=working_dir

        # set icon application
        self.ui.setWindowIcon(QtGui.QIcon(resource_path("inti_logo.png")))
    
        
        # recupere la position
        self.read_settings()
        
        self.ui.inti_view.ui.roiBtn.hide()
        self.ui.inti_view.ui.menuBtn.hide()
        self.ui.inti_view.sigTimeChanged.connect(self.frame_changed)
        self.ui.inti_view.scene.sigMouseMoved.connect(self.on_mouse_move)
        
        # Create a keyboard shortcut 
        shortcut = QtGui.QKeySequence("Escape")
        self.shortcut = QtGui.QShortcut(shortcut, self.ui)
        self.shortcut.activated.connect(self.emit_on_ferme)
        
    def emit_on_ferme(self) :
        #print("emit")
        self.on_ferme.emit()
    
    def set_img(self, img_data) :
        img_proc = np.fliplr(np.rot90(img_data, 3))
        self.ui.inti_view.setImage(img_proc)
    
    def set_vol(self, img_data) :
        #img_proc = np.fliplr(np.rot90(img_data, 3))
        self.ui.inti_view.setImage(img_data)

    def on_mouse_move (self, pos):
        if self.ui.inti_view.imageItem.sceneBoundingRect().contains(pos) :
            mouse_point= self.ui.inti_view.view.mapSceneToView(pos)
            x,y =int(mouse_point.x()), int(mouse_point.y())
            
            # on visualise l'intensité
            if 0 <= x < self.ui.inti_view.image.shape[0] and 0<= y < self.ui.inti_view.image.shape[1] :
                # pour affichage premiere ligne n'est pas 0 mais 1
                msg="x : "+str(x+1)+' , y : '+str(y+1)

                pix_value = self.ui.inti_view.image[x,y]
                try :
                    if len(pix_value) != 1:
                        msg=msg+' , R : '+str(int(pix_value[0]))+ ' , G : '+str(int(pix_value[1]))+' , B : '+str(int(pix_value[2]))
                except :
                    msg=msg+' , I : '+str(int(pix_value))

                self.ui.statusbar.showMessage(self.nomfich+'  '+msg)
            else:
                #print ("mouse out of bounds")
                self.ui.statusbar.showMessage(self.nomfich)
                    
                    
        
    def frame_changed(self) :
        test=False
        if test :
            trame_index=self.ui.inti_view.currentIndex
            vol_img=self.ui.inti_view.image
            #my_trame = vol_img[trame_index]
        else :
            pass
    
    def show(self) :
        self.ui.show()
        
    def open_in_tab(self) :
        self.on_ferme.emit()

    def mon_closeEvent (self,event):
        
        self.write_settings()
        #self.on_ferme.emit()

        
    def saveas (self) :

        pos=self.nomfich.rfind('.')
        ext = self.nomfich[pos+1:]
        nom_suggere =self.working_dir+os.sep+self.nomfich[:pos]
        
        file_name,_=QFileDialog.getSaveFileName(self, self.tr("Sauver fichier png"), nom_suggere, self.tr("Fichiers png (*.png);;Tous les fichiers (*)"))
        if file_name :
            print(file_name)
            if ext == 'ser' :
                index = self.ui.inti_view.currentIndex
                myimage=self.ui.inti_view.image[index]
            else :
                myimage=self.ui.inti_view.image
            myimage=np.flipud(np.rot90(myimage))
            if len(myimage.shape)==3 :
                #ajuste les seuils
                levels = self.ui.inti_view.getLevels()
                sbas,shaut = levels
                if shaut != sbas :
                    myimage = np.clip((myimage.astype(np.float32)-sbas)/(shaut-sbas),0,1)
                    myimage = (myimage*256).astype(np.uint8)
                myimage=cv2.cvtColor(myimage, cv2.COLOR_BGR2RGB)
                cv2.imwrite(file_name, myimage)
            else :
                # ajustment des seuils
                levels = self.ui.inti_view.getLevels()
                sbas,shaut = levels
                if shaut != sbas :
                    myimage = np.clip((myimage-sbas)/(shaut-sbas)*65535,0,65535).astype(np.uint16)
                cv2.imwrite(file_name, myimage)

    def read_settings(self):
        settings=QSettings("Desnoux Buil", "inti_partner")
        self.ui.restoreGeometry(settings.value("ImgWindow/geometry"))
        self.ui.restoreState(settings.value("ImgWindow/windowState"))
    
    def write_settings(self) :
        # sauve settings
        settings=QSettings("Desnoux Buil", "inti_partner")
        settings.setValue("ImgWindow/geometry", self.ui.saveGeometry())
        settings.setValue("ImgWindow/windowState", self.ui.saveState())
        
    def set_title (self, title ):
        self.nomfich = title
        self.ui.setWindowTitle(title)
        self.ui.statusbar.showMessage(title)


        
    def set_pos (self, posx,posy) :
        self.ui.move(posx,posy)


class gong_wnd(QDialog) :

    
    def __init__(self):
        super(gong_wnd, self).__init__()
       
        
        #fichier GUI par Qt Designer
        loader = QUiLoader()
        ui_file_name=resource_path('gong.ui')
        ui_file = QFile(ui_file_name)
        
        if not ui_file.open(QIODevice.ReadOnly):
            print(f"Cannot open {ui_file_name}: {ui_file.errorString()}")
            sys.exit(-1)
        
        self.ui = loader.load(ui_file)
        
        ui_file.close()
        
        # connect signaux boutons
        self.ui.gong_GD_btn.clicked.connect(self.gong_gd)
        self.ui.gong_HB_btn.clicked.connect(self.gong_hb)
        #self.ui.gong_apply_btn.clicked.connect(self.update_ori_image)
        
        # init nb inversions
        self.nb_ns=0
        self.nb_ew = 0 
        
        self.ui.move(10,10)
        
    def update_inversions(self, inv) :
        self.inv = inv
        self.ui.gong_inversions_lbl.setText('Inversions proposées : '+ inv)
    
    def update_ori_image (self):
        inv=self.inv
        if self.inv != 'None' :
            mypixmap= self.ui.gong_myimg_lbl.pixmap()
            if inv == 'NS' :
               flipped = mypixmap.transformed(QtGui.QTransform().scale(1,-1))
               self.nb_ns=self.nb_ns+1
            if inv == 'EW' :
               flipped = mypixmap.transformed(QtGui.QTransform().scale(-1,1))
               self.nb_ew=self.nb_ew+1
            if inv == 'NS-EW' :
               flipped = mypixmap.transformed(QtGui.QTransform().scale(-1,-1))
               self.nb_ns=self.nb_ns+1
               self.nb_ew=self.nb_ew+1
            
            self.ui.gong_myimg_lbl.setPixmap(flipped)
    
    def gong_gd (self):
        mypixmap= self.ui.gong_myimg_lbl.pixmap()
        flipped = mypixmap.transformed(QtGui.QTransform().scale(-1,1))
        self.nb_ew=self.nb_ew+1
        self.ui.gong_myimg_lbl.setPixmap(flipped)
    
    def gong_hb (self):
        mypixmap= self.ui.gong_myimg_lbl.pixmap()
        flipped = mypixmap.transformed(QtGui.QTransform().scale(1,-1))
        self.nb_ns=self.nb_ns+1
        self.ui.gong_myimg_lbl.setPixmap(flipped)
        
    def get_inversions (self) :
        inv_to_return = [self.nb_ns%2, self.nb_ew%2]
        return inv_to_return
    
    def show(self):
        self.ui.show()
        




# ----------------------------------------------------------------------------
# class infos_dlg  fenetre affichage zone label pour texte
#-----------------------------------------------------------------------------

class infos_dlg(QDialog) :
    
    def __init__(self):
        super(infos_dlg, self).__init__()
        
        #fichier GUI par Qt Designer
        loader = QUiLoader()
        ui_file_name=resource_path('infos_txt.ui')
        ui_file = QFile(ui_file_name)
        
        if not ui_file.open(QIODevice.ReadOnly):
            print(f"Cannot open {ui_file_name}: {ui_file.errorString()}")
            sys.exit(-1)
        
        self.ui = loader.load(ui_file)
        
        ui_file.close()
        self.ui.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.ui.show()
        
    def display_infos_log (self, fich) :
        try:
            #with open(fich, encoding ='latin-1') as f:
            with open(fich, encoding ='utf-8') as f:
                log_txt= f.read()
            self.ui.infos_lbl.setText(log_txt)
        except :
            try :
                #with open(fich, encoding ='latin-1') as f:
                with open(fich, encoding ='latin-1') as f:
                    log_txt= f.read()
                self.ui.infos_lbl.setText(log_txt)
            except :
                print("Erreur fichier log")

    def display_infos_fits (self, header) :
        try :
            # separe mots clef et valeurs
            hdr_txt = "\n".join(f"{cle} : {valeur}" for cle, valeur in header.items())
            self.ui.infos_lbl.setText(hdr_txt)
        except :
            print("Erreur entête fits")



# ----------------------------------------------------------------------------
# class LOG  redirection console to textEdit
#-----------------------------------------------------------------------------
    
class Log(object):
    def __init__(self, edit):
        self.out = sys.stdout
        self.textEdit = edit

    def write(self, message):
        self.out.write(message)
        #self.textEdit.append(message)
        self.textEdit.moveCursor(QtGui.QTextCursor.End) 
        self.textEdit.insertPlainText( message )

    def flush(self):
        self.out.flush()
    
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
# main App Qt  
#-----------------------------------------------------------------------------  
#-----------------------------------------------------------------------------  

def file_exist(name):    
   
    if not os.path.exists(name):

        #print('ERROR: File ' + name + ' not found.')
        #print('End.') 
        return  False
    else:
        return True

# from J.Meeus
def angle_P_B0 (date_utc):
    time = astropy.time.Time(date_utc)
    myJD=time.jd
    #myJD= 2460711.9700
    #date_1853JD2=2398167.2763889 # ref 9 nov 1853 18:37 
    #theta = ((myJD - date_1853JD2) /27.2743) +1
    #a=360*(theta-int(theta))
    #L0=360-a
    theta0 = (myJD - 2398220) * 360/25.38
    Rot_Carrington= (myJD-2398140.2270)/27.2752316 #JMeeus 2nd edition p191

    I = 7.25
    K = 73.6667 + 1.3958333*(myJD - 2396758)/36525
    T = (myJD - 2451545)/36525
    Lo = (0.0003032*T + 36000.76983)*T + 280.46645
    M = ((-0.00000048*T - 0.0001559)*T + 35999.05030)*T + 357.52910
    C = ((-0.000014*T - 0.004817)*T + 1.914600)*math.sin(math.radians(M))
    #C = C +(-0.000101*T - 0.019993)*math.sin(math.radians(2*M)) + 0.000290*math.sin(math.radians(3*M))
    C = C +(-0.000101*T + 0.019993)*math.sin(math.radians(2*M)) + 0.000290*math.sin(math.radians(3*M)) #Jmeeus p164
    S_true_long = Lo + C
    Lambda = S_true_long - 0.00569 - 0.00478*math.sin(math.radians(125.04 - 1934.136*T))
    Lambda_cor = Lambda + 0.004419
    x = math.degrees(math.atan(-math.cos(math.radians(Lambda_cor)) * math.tan(math.radians(23.440144))))
    y = math.degrees(math.atan(-math.cos(math.radians(Lambda - K)) * math.tan(math.radians(I))))
    P = x + y
    Bo = math.degrees(math.asin(math.sin(math.radians(Lambda - K)) * math.sin(math.radians(I))))
    eta= math.degrees(math.atan(math.tan(math.radians(Lambda - K)) * math.cos(math.radians(I))))
    a = theta0 /360
    theta=(a-int(a))*360
    L0= eta - theta
    if L0 <0 :
        L0=L0+360
    
    return(str(round(P,2)),str(round(Bo,2)), str(round(L0,2)), str(int(Rot_Carrington)))

def img_rotate(frame, angle_rot, centreX, centreY, diam) :
    # on copie l'image de travail et on recupere hauteur et largeur
    fr_avant_rot=np.copy(frame)
    hh,ww=fr_avant_rot.shape[:2]

    if diam !=0 :
        if diam>frame.shape[0] :
            h_bande = int(abs((abs((np.sin(np.deg2rad(angle_rot))* diam)))-centreY)+20)
            bandeau= np.zeros((h_bande,frame.shape[1]), dtype='uint16')
            fr_avant_rot=np.vstack([bandeau, frame, bandeau])
            hh,ww=fr_avant_rot.shape[:2]
            centreX=fr_avant_rot.shape[1]//2 
            centreY=fr_avant_rot.shape[0]//2 
    
    # calcul de la matrice de rotation, angle en degre
    rotation_mat=cv2.getRotationMatrix2D((centreX,centreY),float(angle_rot),1.0)
    
    # application de la matrice de rotation
    fr_rot=cv2.warpAffine(fr_avant_rot,rotation_mat,(ww,hh),flags=cv2.INTER_LINEAR)
    frame=np.array(fr_rot, dtype='uint16')
    
    return frame

def gong (fits_dateobs, filename, curr_dir) :
    fmt = '%Y%m%d'
    #date_obs='20211213'
    #fits_dateobs=values['-DATEOBS-']
    if fits_dateobs!='' :
        datemonth=fits_dateobs.split('T')[0].replace('-','')[:6]
        dateday=fits_dateobs.split('T')[0].replace('-','')
        r1="https://gong2.nso.edu/HA/hag/"+datemonth+"/"+dateday+"/"
        Vo_req=r1

        reponse_web=rq.get(Vo_req)
        sun_meudon=reponse_web.text.split("\n")
        t=sun_meudon[11].split('href=')[1].split(">")[0]
        t=t.replace('"','')
        web.open(r1+t)
        
        

def helium_seg (frame,R) :
    debug =False
    s=0
    # segmentation disque helium
    mask=disk_level_set(frame.shape, radius=float(R))
    if debug :
        plt.title("disk")
        plt.imshow(mask)
        plt.show()

    return s, mask

def pic_histo (frame) :
    # seuil adaptatif à partir histogram
    debug= False
    
    #calcul histo
    f=frame/256
    f_8=f.astype('uint8')
    th_otsu,mask=cv2.threshold(f_8, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    hist = cv2.calcHist([f_8],[0],None,[256],[0,256])
    
    if debug :
        plt.title("hist 1"+ str(th_otsu))
        plt.plot(hist)
        plt.show()
     
    
    hist[0:int(th_otsu)]=0
    pos_max=np.argmax(hist)
    seuil_haut=(pos_max*256)
          
    if debug  :
        plt.title("histflat  "+ str(pos_max))
        plt.plot(hist)
        plt.show()
     
    return seuil_haut, mask

def helium_flat (img, seuil, mask ):
    
    debug=False
    
    ih, iw=img.shape
    
    if debug:
        plt.imshow(img)
        plt.show()
    
    #chull=convex_hull_image(mask)
    chull=np.where(mask==0,False,True)
    
    if debug :
        plt.title("chull")
        plt.imshow(chull)
        plt.show()

    
    img_m=img*chull
    m = np.ma.masked_equal(img_m, 0)
    med=np.ma.median(m, 1)
    med2=med.filled(1)
    med2=np.array(med2, dtype='uint16')
    
    if debug :
        plt.plot(med2)
        plt.show()
        
    # Génère tableau image de flat 
    flat=[]
    flat=np.tile(med2,(iw,1))
        
    np_flat=np.asarray(flat)
    flat = np_flat.T
    
    # Evite les divisions par zeros...
    flat=flat*chull
    flat[flat==0]=1
    
    if debug:
        plt.title("flat")
        plt.imshow(flat)
        plt.show()

    # Divise image par le flat
    BelleImage=np.divide(img,flat)
    BelleImage[BelleImage>2]=0
    BelleImage=BelleImage*37267
    neg_chull=invert(chull)
    bi=img*neg_chull+BelleImage
    bi=np.array(bi, dtype='uint16')
    
    if debug :
        plt.imshow(bi)
        plt.show()
        
    #BelleImage[BelleImage>65535]=65535 # bug saturation
    frame=np.array(bi, dtype='uint16')  
  
    
    return frame, chull, neg_chull, BelleImage


def corrige_trans_helium (img, R) :
    # créer le mask à partir du rayon
    debug =False
    
    ih, iw=img.shape
    # segmentation disque helium
    mask=disk_level_set(img.shape, radius=float(R))

    chull=np.where(mask==0,False,True)
    
    if debug :
        plt.title("chull")
        plt.imshow(chull)
        plt.show()

    img_m=img*chull
    m = np.ma.masked_equal(img_m, 0)
    med=np.ma.median(m, 1)
    med2=med.filled(1)
    med2=np.array(med2, dtype='uint16')
    
    # Génère tableau image de flat 
    flat=[]
    flat=np.tile(med2,(iw,1))
        
    np_flat=np.asarray(flat)
    flat = np_flat.T
    
    # Evite les divisions par zeros...
    flat=flat*chull
    flat[flat==0]=1
    
    if debug:
        plt.title("flat")
        plt.imshow(flat)
        plt.show()

    # Divise image par le flat
    BelleImage=np.divide(img,flat)
    BelleImage[BelleImage>2]=0 # was 2
    BelleImage=BelleImage*37267
    neg_chull=invert(chull)
    bi=img*neg_chull+BelleImage
    bi=np.array(bi, dtype='uint16')
    
    if debug :
        plt.imshow(bi)
        plt.show()
        
    #BelleImage[BelleImage>65535]=65535 # bug saturation
    frame=np.array(bi, dtype='uint16')
    
    return frame   

def seuil_image_force (img, Seuil_haut, Seuil_bas):
    img[img>Seuil_haut]=Seuil_haut
    img_seuil=(img-Seuil_bas)* (65535/(Seuil_haut-Seuil_bas)) # was 65500
    img_seuil[img_seuil<0]=0
    
    return img_seuil

def create_circular_mask(image_shape, center, radius, feather_width):
    """
    Create a circular mask with progressive edges (feathering).

    Parameters:
        image_shape (tuple): Shape of the target image (height, width).
        center (tuple): Center of the circular mask (x, y).
        radius (int): Radius of the circular mask.
        feather_width (int): Width of the feathering at the edges.

    Returns:
        mask (numpy.ndarray): A 2D mask with values ranging from 0 to 1.
    """
    height, width = image_shape
    y, x = np.ogrid[:height, :width]
    dist_from_center = np.sqrt((x - center[0]) ** 2 + (y - center[1]) ** 2)

    # Create a mask with feathering
    mask = np.clip((radius + feather_width - dist_from_center) / feather_width, 0, 1)
    return mask

def blend_images(cc, result_image, mask):
    """
    Blend two images using a circular mask.

    Parameters:
        cc (numpy.ndarray): The background image.
        result_image (numpy.ndarray): The foreground image to be masked in the center.
        mask (numpy.ndarray): The blending mask with values between 0 and 1.

    Returns:
        blended_image (numpy.ndarray): The final blended image.
    """
    # Ensure both images are float64 for blending
    cc = cc.astype(np.float64)
    result_image = result_image.astype(np.float64)

    # Blend the images using the mask
    blended_image = mask * result_image + (1 - mask) * cc

    # Clip values to 16-bit range and convert back to uint16
    blended_image = np.clip(blended_image, 0, 65535).astype(np.uint16)

    return blended_image

def Colorise_Image (couleur, frame_contrasted):
    
    # gestion couleur auto ou sur dropdown database compatibility
    # 'On','H-alpha','Pale','Calcium','Sodium','Magnesium'
    # 'On' active le mode auto de detection de couleur
 
    f=frame_contrasted/256
    f_8=f.astype('uint8')
    
    #hist = cv2.calcHist([f_8],[0],None,[256],[10,256])
    # separe les 2 pics fond et soleil
    th_otsu,img_binarized=cv2.threshold(f_8, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    hist = cv2.calcHist([f_8],[0],None,[256],[0,256])
    hist2=np.copy(hist)
    hist2[0:int(th_otsu)]=0
    pos_max=np.argmax(hist2)

    debug=False
    if debug :
        plt.plot(hist2)
        plt.show()
        print('couleur : ',pos_max)

    
    # test ombres >> provoque des applats 
    ombres=False
    if ombres :
        
        i_low=[]
        i_hi=[]
        fr=np.copy(frame_contrasted)
        i_low=np.array((fr<(pos_max*256))*fr*1.01, dtype='uint16')
        i_hi=(fr>=pos_max)*fr
        fr=i_low+i_hi
        f=fr/256
        f_8=f.astype('uint8')
    
    
    if couleur =='on' :  
        if pos_max<200 and pos_max>=98 : #was 70
            couleur="H-alpha"
        if pos_max<98 :
            couleur="Calcium"
        if pos_max>=200 :
            couleur="Pale"

    
    # test ombres >> provoque des applats 
    ombres=False
    if ombres :
        f8_low=[]
        f8_hi=[]
        f8_low=np.array((f_8<pos_max)*f_8*1.05, dtype='uint8')
        f8_hi=(f_8>=pos_max)*f_8
        f_8=f8_low+f8_hi
    
    
    #couleur="H-alpha"
    
    if couleur != '' :
        # image couleur en h-alpha
        if couleur == 'H-alpha' :
            # build a lookup table mapping the pixel values [0, 255] to
            # their adjusted gamma values
            gamma=0.3   # was gam 1.3 > 0.3 ok un peu plus clair et 0.1 plus sombre sombre
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f1_gam= cv2.LUT(f_8, table)
            
            gamma=0.55 # was gam 0.5 - 0.3 trop rouge, 0.6 un peu jaune - 0.55 ok
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f2_gam= cv2.LUT(f_8, table)
            
            gamma=1 # gam is 1.0
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f3_gam= cv2.LUT(f_8, table)
            
            i1=(f1_gam*0.1).astype('uint8')     # was 0.05 - 1 trop pale - 0.1 ok
            i2=(f2_gam*1).astype('uint8')       # is 1
            i3=(f3_gam*1).astype('uint8')       # is 1
            
            gamma=1.5 # gam total image 2 est trop fade, 1.2 pas assez, 1.5 pas mal
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            i1= cv2.LUT(i1, table)
            i2= cv2.LUT(i2, table)
            i3= cv2.LUT(i3, table)
            
            img_color=np.zeros([frame_contrasted.shape[0], frame_contrasted.shape[1], 3],dtype='uint8')
            img_color[:,:,2] = np.array(i1, dtype='uint8') # blue
            img_color[:,:,1] = np.array(i2, dtype='uint8') # green
            img_color[:,:,0] = np.array(i3, dtype='uint8') # red
            
            # gestion gain alpha et luminosité beta
            #alpha=(255//2+10)/pos_max
            #print('alpha ', alpha)
            #img_color=cv2.convertScaleAbs(img_color, alpha=alpha, beta=0) # was 1.3 - 1.1 plus sombre - 1.2 ok
            
            # affiche dans clahe window for test
            #cv2.imshow('clahe',img_color)
            #cv2.setWindowTitle("clahe", "color")

            
        # image couleur en calcium
        if couleur == 'Calcium' :
            # build a lookup table mapping the pixel values [0, 255] to
            # their adjusted gamma values
            gamma=1.2  # was 1
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f1_gam= cv2.LUT(f_8, table)
            
            gamma=1 # was 0.8
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f2_gam= cv2.LUT(f_8, table)
            
            gamma=1 # was 0.8
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f3_gam= cv2.LUT(f_8, table)
            
            # i1: bleu, i2: vert, i3:rouge
            i1=(f1_gam*1).astype('uint8')     # was 0.05 - 1 trop pale - 0.1 ok
            i2=(f2_gam*0.7).astype('uint8')       # is 1
            i3=(f3_gam*0.7).astype('uint8')       # was 0.8 un peu trop violet
            
            gamma=1 # gam total image finalement aucun, 1.2 un peu fade
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            i1= cv2.LUT(i1, table)
            i2= cv2.LUT(i2, table)
            i3= cv2.LUT(i3, table)
            
            img_color=np.zeros([frame_contrasted.shape[0], frame_contrasted.shape[1], 3],dtype='uint8')
            img_color[:,:,2] = np.array(i1, dtype='uint8') # blue
            img_color[:,:,1] = np.array(i2, dtype='uint8') # green
            img_color[:,:,0] = np.array(i3, dtype='uint8') # red
            
            vp=np.percentile(f_8, 99.7)
            alpha=(255//2)/(vp*0.5)
            #print('alpha ', alpha)
            
            img_color=cv2.convertScaleAbs(img_color, alpha=alpha) # was 1.5 ok
            
            # affiche dans clahe window for test
            #cv2.imshow('clahe',img_color)
            #cv2.setWindowTitle("clahe", "color")
        
        # image couleur en calcium
        if couleur == 'H Beta' or couleur == 'H Béta':
            # build a lookup table mapping the pixel values [0, 255] to
            # their adjusted gamma values
            gamma=1.2  # was 1
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f1_gam= cv2.LUT(f_8, table)
            
            gamma=1 # was 0.8
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f2_gam= cv2.LUT(f_8, table)
            
            gamma=1 # was 0.8
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f3_gam= cv2.LUT(f_8, table)
            
            # i1: bleu, i2: vert, i3:rouge
            i1=(f1_gam*1).astype('uint8')     # was 1
            i2=(f2_gam*0.7).astype('uint8')       # was 0.7
            i3=(f3_gam*0.5).astype('uint8')       # was 0.5
            
            gamma=0.7 # gam total image finalement aucun, 1.2 un peu fade
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            i1= cv2.LUT(i1, table)
            i2= cv2.LUT(i2, table)
            i3= cv2.LUT(i3, table)
            
            img_color=np.zeros([frame_contrasted.shape[0], frame_contrasted.shape[1], 3],dtype='uint8')
            img_color[:,:,2] = np.array(i1, dtype='uint8') # blue
            img_color[:,:,1] = np.array(i2, dtype='uint8') # green
            img_color[:,:,0] = np.array(i3, dtype='uint8') # red
            
            #vp=np.percentile(f_8, 99.7)
            #alpha=(255//2)/(vp*0.5)
            #print('alpha ', alpha)
            
            #img_color=cv2.convertScaleAbs(img_color, alpha=alpha) # was 1.5 ok

        
        # image couleur en quasi blanc (continuum)
        if couleur == 'Pale' :
            # build a lookup table mapping the pixel values [0, 255] to
            # their adjusted gamma values
            gamma=1  # 
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f1_gam= cv2.LUT(f_8, table)
            
            gamma=1 # was 0.7
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f2_gam= cv2.LUT(f_8, table)
            
            gamma=1 # 
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f3_gam= cv2.LUT(f_8, table)
            
            # i1: bleu, i2: vert, i3:rouge
            i1=(f1_gam*0.92).astype('uint8')     # was 0.5 
            i2=(f2_gam*0.98).astype('uint8')       # was 0.9
            i3=(f3_gam*1).astype('uint8')       # is 1
            
            gamma=0.5 # gam total image 1 trop fade, 0.7 pas mal
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            i1= cv2.LUT(i1, table)
            i2= cv2.LUT(i2, table)
            i3= cv2.LUT(i3, table)
            
                
            img_color=np.zeros([frame_contrasted.shape[0], frame_contrasted.shape[1], 3],dtype='uint8')
            img_color[:,:,2] = np.array(i1, dtype='uint8') # blue
            img_color[:,:,1] = np.array(i2, dtype='uint8') # green
            img_color[:,:,0] = np.array(i3, dtype='uint8') # red
            
            #alpha=(255//2+50)/pos_max
            #alpha=1
            #print('alpha ', alpha)
            #img_color=cv2.convertScaleAbs(img_color, alpha=alpha) # was 1
            
        # image couleur en jaune-orange (sodium)
        if couleur == 'Sodium' :
            # table wavelength 590 rgb(255, 223, 0)
            # build a lookup table mapping the pixel values [0, 255] to
            # their adjusted gamma values
            gamma=1  # 
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f1_gam= cv2.LUT(f_8, table)
            
            gamma=1 # was 0.7
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f2_gam= cv2.LUT(f_8, table)
            
            gamma=1 # 
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f3_gam= cv2.LUT(f_8, table)
            
            # i1: bleu, i2: vert, i3:rouge
            i1=(f1_gam*0.3).astype('uint8')    #b was 0.62
            i2=(f2_gam*0.92).astype('uint8')    #g
            i3=(f3_gam*0.96).astype('uint8')    #r 
            
            gamma=0.7 # gam total image 1 trop fade, 0.7 pas mal
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            i1= cv2.LUT(i1, table)
            i2= cv2.LUT(i2, table)
            i3= cv2.LUT(i3, table)
            
                
            img_color=np.zeros([frame_contrasted.shape[0], frame_contrasted.shape[1], 3],dtype='uint8')
            img_color[:,:,2] = np.array(i1, dtype='uint8') # blue
            img_color[:,:,1] = np.array(i2, dtype='uint8') # green
            img_color[:,:,0] = np.array(i3, dtype='uint8') # red
        
        # image couleur en jaune-orange (sodium)
        if couleur == 'Helium' :
            # wavelength 587nm rgb(255, 233, 0)
            # build a lookup table mapping the pixel values [0, 255] to
            # their adjusted gamma values
            gamma=1  # 
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f1_gam= cv2.LUT(f_8, table)
            
            gamma=1 # was 0.7
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f2_gam= cv2.LUT(f_8, table)
            
            gamma=1 # 
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f3_gam= cv2.LUT(f_8, table)
            
            # i1: bleu, i2: vert, i3:rouge
            i1=(f1_gam*0.3).astype('uint8')     # was 0.7
            i2=(f2_gam*0.82).astype('uint8')    # was 0.92
            i3=(f3_gam*0.92).astype('uint8')    # r   
            
            gamma=0.7 # gam total image 1 trop fade, 0.7 pas mal
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            i1= cv2.LUT(i1, table)
            i2= cv2.LUT(i2, table)
            i3= cv2.LUT(i3, table)
            
                
            img_color=np.zeros([frame_contrasted.shape[0], frame_contrasted.shape[1], 3],dtype='uint8')
            img_color[:,:,2] = np.array(i1, dtype='uint8') # blue
            img_color[:,:,1] = np.array(i2, dtype='uint8') # green
            img_color[:,:,0] = np.array(i3, dtype='uint8') # red
            
        # image couleur en jaune-orange (sodium)
        if couleur == 'Magnesium' :
            # build a lookup table mapping the pixel values [0, 255] to
            # their adjusted gamma values
            gamma=1  # 
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f1_gam= cv2.LUT(f_8, table)
            
            gamma=1 # was 0.7
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f2_gam= cv2.LUT(f_8, table)
            
            gamma=1 # 
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            f3_gam= cv2.LUT(f_8, table)
            
            # i1: bleu, i2: vert, i3:rouge
            i1=(f1_gam*0.65).astype('uint8')     
            i2=(f2_gam*0.8).astype('uint8')       
            i3=(f3_gam*0.67).astype('uint8')       
            
            gamma=0.5 # gam total image 1 trop fade, 0.7 pas mal
            invGamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** invGamma) * 255
            for i in np.arange(0, 256)]).astype("uint8")
                # apply gamma correction using the lookup table
            i1= cv2.LUT(i1, table)
            i2= cv2.LUT(i2, table)
            i3= cv2.LUT(i3, table)
                
            img_color=np.zeros([frame_contrasted.shape[0], frame_contrasted.shape[1], 3],dtype='uint8')
            img_color[:,:,2] = np.array(i1, dtype='uint8') # blue
            img_color[:,:,1] = np.array(i2, dtype='uint8') # green
            img_color[:,:,0] = np.array(i3, dtype='uint8') # red
        
        return img_color

def synth_spectrum (template, ratio_pix) :
    # bug fix 12 jan 2025 - ratio_pix was fixed to 0.5
    debug=False
  
    h,w = template.shape[0], template.shape[1]
    
    if ratio_pix !=1 :
        template=cv2.resize(template, dsize=(w, int(h*ratio_pix)), interpolation=cv2.INTER_LANCZOS4)
        template=cv2.GaussianBlur(template,(5,1),cv2.BORDER_DEFAULT)

    #print('Pattern Dimensions : ',template.shape)
    template=template[:,w//2-100:(w//2)+100]
    moy=1*np.mean(template,1)
    moy=np.array(moy, dtype='uint8')
    vector_t= np.array([moy]).T

    temp_r=np.tile(vector_t, (1,400))
    #print('Dimensions : ',temp_r.shape)

    if debug :
        #cv2.imwrite('resized.png', template)
        print('Resized Pattern Dimensions : ',template.shape)
        plt.imshow(template)
        plt.show()
        plt.imshow(temp_r)
        plt.show()
    
    return temp_r

def template_locate (img_r, temp_r) :
    debug=False
    
    if debug :
        plt.imshow(img_r)
        plt.show()
        plt.imshow(temp_r)
        plt.show()
        
    # Trouve la bonne region de temp_r dans le spectre img_r complet 
    matched= cv2.matchTemplate(img_r, temp_r, cv2.TM_CCOEFF_NORMED)
    
    # Coordinates of the bounding box
    (minVal, maxVal, minLoc, maxLoc) = cv2.minMaxLoc(matched)
    
    return maxLoc

def get_baseline (f) :
    f_short=os.path.split(f)[1]
    f_path=os.path.split(f)[0]
    f_short = f_short.removeprefix('st')
    f_short = f_short.removeprefix('cr')
    f=f_path+os.sep+f_short
    
    """
    prefix=f_short.rfind('st')
    if prefix != -1 :
        f_short=f_short[2:]
        f=f_path+os.sep+f_short
    prefix=f_short.rfind('cr')
    if prefix != -1 :
        f_short=f_short[2:]
        f=f_path+os.sep+f_short
    """   
    index=-1
    if f.rfind('_dp') !=1 :
        index=f.rfind('_dp')
    if f.rfind('_color') != -1 :
        index=f.rfind('_color')
    if f.rfind('_doppler') != -1 :
        index =f.rfind('_doppler')
    if index == -1 :
        index=f.rfind("_")
        
    baseline= f[:index] # chemin complet
        
    return baseline

def get_time_from_log (fich):
    # retourne le jour julien et dateobs UTC
    # SER date UTC: sous le format fits date T heure

    try:
        with open(fich, encoding ='latin-1') as f:
            lines_log=f.readlines()
           
            # trouve la ligne avec UTC
            # SER date UTC :"2024-04-13T13:16:33.8371717"
            ligne2=[l  for l in lines_log if "UTC" in l ]
            b=ligne2[0].rstrip()
            # decoupe la ligne apres le 'UTC :' pour la dateTheure format fits
            sc=str(b).split('UTC :')[1][1:-1].split('T')
            #print(sc)
            
            # decode heure
            th=sc[1].split(':')
            sec=th[2].split('.')
            thi=[int(th[0]), int(th[1]), int(sec[0]), int(sec[1][0:5])]
            # decode date
            td=sc[0].split('-')
            tdi=[int(x) for x in td]

            # Perform the calculation
            mydatetime = datetime.datetime(tdi[0], tdi[1], tdi[2], thi[0], thi[1], thi[2], thi[3])
            serial_datetime=mydatetime.timestamp()
            #print(serial_datetime)
        

    except:
        print('Erreur fichier : ', fich)
        serial_datetime = 0
    
    return serial_datetime, sc

def get_geom_from_log (flog) :
    try:
        with open(flog, encoding='latin-1') as f:
            lines_log=f.readlines()
            # trouve la ligne avec centre et rayon
            # ajout ligne pour image croppée
            try :
                ligne2=[l  for l in lines_log if 'xcc,ycc' in l]
            except:
                ligne2=[l  for l in lines_log if 'xc,yc' in l]
            ligne2[0]=ligne2[0].replace('\n','')
            # decoupe la ligne apres le ':' pour les coordonnées du centre xc,yc et rayon
            sc=str(ligne2[0]).split(':')[1].split(' ')
            #print('sc',sc)
            cx=sc[1]
            cy=sc[2]
            sr=sc[3]
            
            # decode haut bas
            # trouve la ligne avec box y1,y2,x1,x2
            maligne1=[l  for l in lines_log if l[0:5]=="Coord" ]
            if len(maligne1) !=0 :
                maligne1[0]=maligne1[0].replace('\n','')
                # decoupe la ligne pour extraire les quatre coordonnées
                bb=str(maligne1[0]).split(':')[1].split(' ')
                box1 = bb[1].split(',')
                box2 = bb[2].split(',')
                ay1=box1[0]
                ay2=box1[1]
                ax1=box2[0]
                ax2=box2[1]
            else :
                ax1=ax2=ay1=ay2=0
    except :
        print('Erreur fichier : ', flog)
        cx=cy=sr=ax1=ax2=ay1=ay2=0
        
    return cx,cy,sr,ay1,ay2,ax1,ax2

    
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

def data_path(relative_path):
    """ Get path to exe, works for dev and for PyInstaller """
    data_path = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]), relative_path))
    return data_path

if __name__ == "__main__":
    
    # ajout d'_internal dans sys.path pour appel avec subprocess
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(__file__)

    internal_path = os.path.join(base_path, "_internal")
    if os.path.isdir(internal_path) and internal_path not in sys.path:
        sys.path.insert(0, internal_path)
    
    # test du type d'execution pour trouver l'emplacement
    # des fichiers une fois compilé avec pyinstaller
    
    
   
    ui_file= True
    
    ## doit etre initialiser ici
    if ui_file==True :
        loader = QUiLoader()    

    # recherche de la langue dans les Qsettings
    try : # au cas ou je ne gere pas bien la valeur par defaut au premier lancement
        settings=QSettings("Desnoux Buil", "inti_partner")
        #LG = settings.value("App/lang",'Fr') # LG est 'Fr' (par defaut) ou 'En'
        LG = settings.value("App/lang")
        #print(LG)
    except :
        LG='Fr'
        
    # pour eviter de devoir tuer app qt sous spyder
    app = QApplication.instance() 
    if not app:

        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    
    app.setStyle('fusion') # pour forcer un beau look sur Mac
    
    
    if LG=='En':
        translator=QTranslator(app)
        translation_ok = translator.load(resource_path('inti_partner_EN.qm'))
        if translation_ok :
            app.installTranslator(translator)
        else:
            print('Err : '+ resource_path('inti_partner_EN.qm'))
    
    my_wnd_class=main_wnd_UI() 

    my_wnd_class.show()
    
    sys.exit(app.exec())
    
    # retour a la redirection des prints sur la console systeme
    sys.stdout=sys.__stdout__
